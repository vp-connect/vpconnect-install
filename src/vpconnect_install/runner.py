"""
Оркестрация одного прогона: SSH, bootstrap vpconnect-configure 00–03, шаги 04–08, артефакты.

См. :mod:`vpconnect_install.configure_bootstrap` и :mod:`vpconnect_install.vpconfigure_provision`.
"""

from __future__ import annotations

import shlex
import time
from collections.abc import Callable
from pathlib import Path

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.configure_bootstrap import run_vpconnect_configure_bootstrap
from vpconnect_install.domain_client import resolve_domain_fqdn
from vpconnect_install.outputs import (
    AccessFileState,
    ArtifactBundle,
    check_artifacts_base_writable,
    default_artifacts_base,
    prepare_artifact_dir,
    write_access_file,
    write_secret_file,
)
from vpconnect_install.ssh_session import SSHSession
from vpconnect_install.version import __version__
from vpconnect_install.vpconfigure_provision import (
    need_run_04_connect,
    run_04_connect_steps,
    run_vpconfigure_phases_05_to_08,
)

LogFn = Callable[[str], None]


def _log_default(_: str) -> None:
    """Пустой логгер по умолчанию, если вызывающий не передал callback."""

    pass


def _resolve_public_target(session: SSHSession, config: ProvisionConfig, log: LogFn) -> str:
    """Определить публичный IPv4 сервера через curl к ifconfig.me / icanhazip; иначе вернуть config.host."""
    cmd = "bash -lc " + shlex.quote(
        "curl -fsS --max-time 10 https://ifconfig.me 2>/dev/null "
        "|| curl -fsS --max-time 10 https://icanhazip.com 2>/dev/null "
        "|| true"
    )
    _code, out, _err = session.exec_command(cmd, timeout=30)
    ip = (out or "").strip()
    if not ip or " " in ip:
        log("[Группа: домен] Не удалось получить публичный IP, используем host.")
        return config.host
    log(f"[Группа: домен] Публичный IP: {ip}")
    return ip


def _want_public_ip(config: ProvisionConfig) -> bool:
    """Нужен ли опрос публичного IP (нет FQDN и ключа домена).

    Да при auto_setup, --use-public-ip или включённой секции домена в GUI.
    """
    if config.domain and config.domain.strip():
        return False
    if config.domain_client_key and config.domain_client_key.strip():
        return False
    return bool(config.auto_setup or config.use_public_ip or config.set_domain)


def _apply_effective_host(session: SSHSession, config: ProvisionConfig, log: LogFn) -> None:
    """Заполнить ``config.effective_domain_or_ip`` по приоритету: FQDN, сервис ключа, публичный IP, SSH host."""
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


def _poll_ssh_after_finalize(
    config: ProvisionConfig,
    post_port: int,
    post_pw: str,
    post_key: str,
    log: LogFn,
) -> SSHSession:
    """Периодически пробовать новое SSH-подключение после смены порта/пароля до таймаута."""
    log("[Подключение] Проверка доступности после смены SSH")
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
    """Закрыть сессию и открыть заново, если менялись порт или пароль root; иначе вернуть ту же сессию."""
    post_port = config.new_ssh_port if config.new_ssh_port is not None else config.port
    post_pw = config.new_root_password.strip() or config.root_password
    post_key = config.root_private_key.strip()
    need_reconnect = post_port != config.port or bool(config.new_root_password.strip())
    if not need_reconnect:
        return session
    session.close()
    return _poll_ssh_after_finalize(config, post_port, post_pw, post_key, log)


def _write_credential_artifacts(
    bundle: ArtifactBundle, config: ProvisionConfig, log: LogFn, *, quiet: bool = False
) -> None:
    """Записать в bundle сгенерированные пароли (root, VPManage), если они есть."""
    if config.new_root_password.strip():
        write_secret_file(bundle, "credentials_new_root_password.txt", config.new_root_password)
        if not quiet:
            log("[Артефакты] Сохранён credentials_new_root_password.txt")
    if config.set_vpmanage and config.vpm_password.strip():
        write_secret_file(bundle, "credentials_vpm_password.txt", config.vpm_password)
        if not quiet:
            log("[Артефакты] Сохранён credentials_vpm_password.txt")


def _persist_run_artifacts(
    bundle: ArtifactBundle,
    config: ProvisionConfig,
    access_state: AccessFileState,
    log: LogFn,
    label: str,
) -> None:
    """Сразу записать файлы паролей и ACCESS.txt (вызывать после каждого значимого шага)."""
    access_state.last_saved_after = label
    _write_credential_artifacts(bundle, config, log, quiet=True)
    write_access_file(bundle, config, access_state)
    log(f"[Артефакты] Сохранены пароли и ACCESS.txt — {label}")


def run(config: ProvisionConfig, log: LogFn | None = None, artifacts_base: Path | None = None) -> Path:
    """
    Выполнить полную установку по ``config``.

    :returns: каталог артефактов (ключи, ACCESS.txt, пароли).
    """
    lg = log or _log_default
    config.apply_auto_setup()
    config.validate()

    base = (artifacts_base if artifacts_base is not None else default_artifacts_base()).resolve()
    check_artifacts_base_writable(base, lg)
    bundle = prepare_artifact_dir(config, base=base)
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
    access_state = AccessFileState()

    def artifact_persist(label: str) -> None:
        _persist_run_artifacts(bundle, config, access_state, lg, label)

    artifact_persist("после создания каталога артефактов и ключей оператора (до SSH)")

    try:
        session.connect()
        lg(
            f"[Версия] Клиент vpconnect-install {__version__}, "
            f"vpconnect-configure (raw): {d.VPCONFIGURE_RAW_GIT_BRANCH}"
        )
        home, os_branch, configure_dir = run_vpconnect_configure_bootstrap(
            session,
            config,
            lg,
            on_script_ok=lambda name: artifact_persist(f"после {name}"),
        )
        _apply_effective_host(session, config, lg)
        artifact_persist("после определения effective host (домен / IP для URL)")

        if need_run_04_connect(config):
            run_04_connect_steps(
                session,
                home,
                configure_dir,
                os_branch,
                config,
                bundle,
                lg,
                config.command_timeout,
                artifact_persist=artifact_persist,
            )
            session = _maybe_reconnect_session(session, config, lg)
        else:
            artifact_persist("04_setsystemaccess.sh не выполнялся (не требуется по конфигурации)")

        run_vpconfigure_phases_05_to_08(
            session,
            configure_dir,
            os_branch,
            config,
            lg,
            config.command_timeout,
            access_state=access_state,
            artifact_persist=artifact_persist,
        )

        return bundle.root
    finally:
        session.close()
