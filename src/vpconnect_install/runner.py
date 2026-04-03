from __future__ import annotations

import shlex
import time
from collections.abc import Callable
from pathlib import Path

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.domain_client import resolve_domain_fqdn
from vpconnect_install.outputs import (
    ArtifactBundle,
    prepare_artifact_dir,
    write_access_file,
    write_secret_file,
)
from vpconnect_install.remote_scripts_fetch import (
    ScriptFetchCache,
    load_script_bytes,
    probe_scripts_available,
)
from vpconnect_install.ssh_session import SSHSession
from vpconnect_install.version import __version__, scripts_git_branch

LogFn = Callable[[str], None]

REMOTE_WORKDIR = d.REMOTE_WORKDIR

SCRIPTS = {
    "base": "base_ufw_prepare.sh",
    "tune": "connect_tune.sh",
    "wg": "wireguard_install.sh",
    "mt": "mtproxy_install.sh",
    "vpm": "vpmanage_install.sh",
    "finalize": "finalize.sh",
}


def _log_default(_: str) -> None:
    pass


def _run_remote_script(
    session: SSHSession,
    script_name: str,
    env_body: str,
    log: LogFn,
    timeout: int,
    *,
    config: ProvisionConfig,
    fetch_cache: ScriptFetchCache,
) -> None:
    branch = scripts_git_branch(__version__)
    script_bytes = load_script_bytes(
        script_name=script_name,
        repo_url=config.scripts_repo_url,
        branch=branch,
        cache=fetch_cache,
        log=log,
        timeout=min(timeout, 120),
    )
    remote_env = f"{REMOTE_WORKDIR}/provision.env"
    remote_script = f"{REMOTE_WORKDIR}/{script_name}"
    session.upload_bytes(remote_env, env_body.encode("utf-8"))
    session.upload_bytes(remote_script, script_bytes)
    inner = (
        f"set -euo pipefail; set -a && source {remote_env} "
        f"&& set +a && bash {remote_script}"
    )
    remote_cmd = (
        f"chmod +x {shlex.quote(remote_script)} && "
        f"bash -lc {shlex.quote(inner)}"
    )
    rc = session.run_remote_shell(remote_cmd, timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"Remote script {script_name} failed with exit code {rc}")


def _build_env(config: ProvisionConfig, bundle: ArtifactBundle) -> str:
    eff = config.effective_domain_or_ip or config.host
    lines: list[str] = []

    def add(key: str, value: str | int) -> None:
        lines.append(f"export {key}={shlex.quote(str(value))}")

    new_port = config.new_ssh_port
    apply_port = 1 if new_port is not None else 0
    np = new_port if new_port is not None else config.port
    apply_pw = 1 if config.new_root_password.strip() else 0

    add("INITIAL_SSH_PORT", config.port)
    add("APPLY_NEW_SSH_PORT", apply_port)
    add("NEW_SSH_PORT", np)
    add("APPLY_NEW_ROOT_PASSWORD", apply_pw)
    add("NEW_ROOT_PASSWORD", config.new_root_password)
    add("SSH_PUBLIC_KEY", bundle.public_key_openssh)
    add("EXTRA_SSH_PUBLIC_KEY", config.new_ssh_public_key.strip())
    add("SET_WIREGUARD", 1 if config.set_wireguard else 0)
    add("WG_PORT", config.wg_port)
    add("WG_CLIENT_CERT_PATH", config.wg_client_cert_path)
    add("WG_CLIENT_CONFIG_PATH", config.wg_client_config_path)
    add("SET_MTPROXY", 1 if config.set_mtproxy else 0)
    add("MTPROXY_PORT", config.mtproxy_port)
    add("SET_VPMANAGE", 1 if config.set_vpmanage else 0)
    add("HTTP_PORT", config.vpm_http_port)
    add("GIT_URL", config.git_url)
    add("GIT_BRANCH", config.git_branch)
    add("INSTALL_PATH", config.install_path)
    add("SYSTEMD_SERVICE", config.systemd_service)
    add("APP_DOMAIN", eff)
    add("APP_PASSWORD", config.vpm_password)
    add("EFFECTIVE_HOST", eff)
    add("STATEDIR", REMOTE_WORKDIR)
    add("HAS_WG", 1 if config.set_wireguard else 0)
    add("HAS_MT", 1 if config.set_mtproxy else 0)
    add("HAS_VPM", 1 if config.set_vpmanage else 0)
    add("MTPROXY_SYSTEMD_SERVICE", d.MTPROXY_SYSTEMD_SERVICE)
    return "\n".join(lines) + "\n"


def _resolve_public_target(session: SSHSession, config: ProvisionConfig, log: LogFn) -> str:
    cmd = (
        "bash -lc "
        + shlex.quote(
            "curl -fsS --max-time 10 https://ifconfig.me 2>/dev/null "
            "|| curl -fsS --max-time 10 https://icanhazip.com 2>/dev/null "
            "|| true"
        )
    )
    _code, out, _err = session.exec_command(cmd, timeout=30)
    ip = (out or "").strip()
    if not ip or " " in ip:
        log("[Группа: домен] Не удалось получить публичный IP, используем host.")
        return config.host
    log(f"[Группа: домен] Публичный IP: {ip}")
    return ip


def _want_public_ip(config: ProvisionConfig) -> bool:
    if config.domain and config.domain.strip():
        return False
    if config.domain_client_key and config.domain_client_key.strip():
        return False
    return bool(config.auto_setup or config.use_public_ip or config.set_domain)


def _apply_effective_host(session: SSHSession, config: ProvisionConfig, log: LogFn) -> None:
    if config.domain and config.domain.strip():
        config.effective_domain_or_ip = config.domain.strip()
        log(f"[Группа: домен] Указанный FQDN: {config.effective_domain_or_ip}")
        return
    if config.domain_client_key and config.domain_client_key.strip():
        try:
            fqdn = resolve_domain_fqdn(config.domain_client_key)
            config.effective_domain_or_ip = fqdn
            log(f"[Группа: домен] FQDN по ключу сервиса: {config.effective_domain_or_ip}")
        except Exception as ex:
            log(f"[Группа: домен] Ошибка сервиса домена: {ex}, используем host.")
            config.effective_domain_or_ip = config.host
        return
    if _want_public_ip(config):
        config.effective_domain_or_ip = _resolve_public_target(session, config, log)
        return
    config.effective_domain_or_ip = config.host
    log(f"[Группа: домен] Используем host: {config.effective_domain_or_ip}")


def _download_wg_public_key(session: SSHSession, log: LogFn) -> str | None:
    try:
        raw = session.download_bytes(f"{REMOTE_WORKDIR}/wg_public.key")
        return raw.decode("utf-8", errors="replace").strip()
    except Exception as ex:
        log(f"[Группа: WireGuard] Не прочитан wg_public.key: {ex}")
        return None


def _download_mtproxy_secret(session: SSHSession, log: LogFn) -> str | None:
    try:
        sec_raw = session.download_bytes(f"{REMOTE_WORKDIR}/mtproxy_secret.txt")
        return sec_raw.decode("utf-8", errors="replace").strip()
    except Exception as ex:
        log(f"[Группа: MTProxy] Не прочитан secret: {ex}")
        return None


def _run_optional_wireguard(
    session: SSHSession,
    config: ProvisionConfig,
    env_body: str,
    log: LogFn,
    fetch_cache: ScriptFetchCache,
) -> str | None:
    if not config.set_wireguard:
        return None
    log("[Группа: WireGuard] Подзадача: установка и клиентские файлы на сервере")
    _run_remote_script(
        session,
        SCRIPTS["wg"],
        env_body,
        log,
        config.command_timeout,
        config=config,
        fetch_cache=fetch_cache,
    )
    return _download_wg_public_key(session, log)


def _run_optional_mtproxy(
    session: SSHSession,
    config: ProvisionConfig,
    env_body: str,
    log: LogFn,
    fetch_cache: ScriptFetchCache,
) -> str | None:
    if not config.set_mtproxy:
        return None
    log("[Группа: MTProxy] Подзадача: сборка и systemd")
    _run_remote_script(
        session,
        SCRIPTS["mt"],
        env_body,
        log,
        config.command_timeout,
        config=config,
        fetch_cache=fetch_cache,
    )
    return _download_mtproxy_secret(session, log)


def _run_optional_vpmanage(
    session: SSHSession,
    config: ProvisionConfig,
    env_body: str,
    log: LogFn,
    fetch_cache: ScriptFetchCache,
) -> None:
    if not config.set_vpmanage:
        return
    log("[Группа: VPManage] Подзадача: git, venv, systemd")
    _run_remote_script(
        session,
        SCRIPTS["vpm"],
        env_body,
        log,
        config.command_timeout,
        config=config,
        fetch_cache=fetch_cache,
    )


def _run_finalize(
    session: SSHSession,
    config: ProvisionConfig,
    env_body: str,
    log: LogFn,
    fetch_cache: ScriptFetchCache,
) -> None:
    log("[Финализация] Перезапуск sshd, ufw enable, отчёт")
    try:
        _run_remote_script(
            session,
            SCRIPTS["finalize"],
            env_body,
            log,
            config.command_timeout,
            config=config,
            fetch_cache=fetch_cache,
        )
    except (TimeoutError, OSError, EOFError) as ex:
        log(f"[Финализация] Соединение могло оборваться после restart sshd: {ex}")


def _poll_ssh_after_finalize(
    config: ProvisionConfig,
    post_port: int,
    post_pw: str,
    post_key: str,
    log: LogFn,
) -> SSHSession:
    log("[Подключение] Проверка доступности после финализации")
    new_session = SSHSession(
        config.host,
        post_port,
        "root",
        password=post_pw,
        private_key_path=post_key,
        private_key_passphrase=config.root_private_key_passphrase,
        connect_timeout=config.ssh_connect_timeout,
        log=log,
    )
    deadline = time.monotonic() + float(config.reboot_wait_timeout)
    while time.monotonic() < deadline:
        if new_session.test_connect():
            try:
                new_session.connect()
                log(f"[Подключение] Снова доступен порт {post_port}")
                return new_session
            except Exception as e:
                log(f"[Подключение] Ожидание SSH: {e}")
        time.sleep(float(config.ssh_poll_interval))
    log("[Подключение] Таймаут ожидания нового SSH (проверьте консоль провайдера)")
    return new_session


def _maybe_reconnect_session(
    session: SSHSession,
    config: ProvisionConfig,
    log: LogFn,
) -> SSHSession:
    post_port = config.new_ssh_port if config.new_ssh_port is not None else config.port
    post_pw = config.new_root_password.strip() or config.root_password
    post_key = config.root_private_key.strip()
    need_reconnect = post_port != config.port or bool(config.new_root_password.strip())
    if not need_reconnect:
        return session
    session.close()
    return _poll_ssh_after_finalize(config, post_port, post_pw, post_key, log)


def _write_credential_artifacts(bundle: ArtifactBundle, config: ProvisionConfig, log: LogFn) -> None:
    if config.new_root_password.strip():
        write_secret_file(bundle, "credentials_new_root_password.txt", config.new_root_password)
        log("[Артефакты] Сохранён credentials_new_root_password.txt")
    if config.set_vpmanage and config.vpm_password.strip():
        write_secret_file(bundle, "credentials_vpm_password.txt", config.vpm_password)
        log("[Артефакты] Сохранён credentials_vpm_password.txt")


def _write_summary_artifacts(
    bundle: ArtifactBundle,
    config: ProvisionConfig,
    mtproxy_secret: str | None,
    wg_pub: str | None,
    log: LogFn,
) -> None:
    write_access_file(
        bundle,
        config,
        mtproxy_secret=mtproxy_secret,
        wireguard_public_key=wg_pub,
    )
    log(f"[Артефакты] Записан {bundle.root / 'ACCESS.txt'}")


def run(config: ProvisionConfig, log: LogFn | None = None, artifacts_base: Path | None = None) -> None:
    lg = log or _log_default
    config.apply_auto_setup()
    config.validate()

    bundle = prepare_artifact_dir(config, base=artifacts_base)
    lg(f"[Артефакты] Каталог: {bundle.root}")

    session = SSHSession(
        config.host,
        config.port,
        "root",
        password=config.root_password,
        private_key_path=config.root_private_key,
        private_key_passphrase=config.root_private_key_passphrase,
        connect_timeout=config.ssh_connect_timeout,
        log=lg,
    )
    mtproxy_secret: str | None = None
    wg_pub: str | None = None

    fetch_cache = ScriptFetchCache()
    branch = scripts_git_branch(__version__)
    try:
        session.connect()
        lg(f"[Версия] Клиент vpconnect-install {__version__}, ветка скриптов в репо: {branch}")
        if config.scripts_repo_url.strip():
            if not probe_scripts_available(
                config.scripts_repo_url, branch, SCRIPTS["base"]
            ):
                lg(
                    f"[Скрипты] Предупреждение: нет ответа 200 для ветки {branch!r} "
                    f"в {config.scripts_repo_url} — проверьте URL и ветку; при сбое скачивания "
                    "будут использованы встроенные скрипты."
                )
        _apply_effective_host(session, config, lg)

        env_body = _build_env(config, bundle)

        lg("[Группа: база] Подзадача: apt и правила UFW (без enable)")
        _run_remote_script(
            session,
            SCRIPTS["base"],
            env_body,
            lg,
            config.command_timeout,
            config=config,
            fetch_cache=fetch_cache,
        )

        lg("[Группа: настройка подключения] Подзадача: пароль, sshd drop-in, authorized_keys")
        _run_remote_script(
            session,
            SCRIPTS["tune"],
            env_body,
            lg,
            config.command_timeout,
            config=config,
            fetch_cache=fetch_cache,
        )

        wg_pub = _run_optional_wireguard(session, config, env_body, lg, fetch_cache)
        mtproxy_secret = _run_optional_mtproxy(session, config, env_body, lg, fetch_cache)
        _run_optional_vpmanage(session, config, env_body, lg, fetch_cache)

        _run_finalize(session, config, env_body, lg, fetch_cache)
        session = _maybe_reconnect_session(session, config, lg)

        _write_credential_artifacts(bundle, config, lg)
        _write_summary_artifacts(bundle, config, mtproxy_secret, wg_pub, lg)
    finally:
        session.close()
