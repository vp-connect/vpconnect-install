"""Запуск скриптов vpconnect-configure 04–08 на сервере после 00–03."""

from __future__ import annotations

import shlex
from collections.abc import Callable
from pathlib import Path

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.configure_bootstrap import (
    INSTALL_ABORTED_MSG,
    _configure_step_failed,
    abort_configure_on_failure,
    exec_vpconfigure_script,
    parse_configure_result_line,
)
from vpconnect_install.outputs import ArtifactBundle
from vpconnect_install.ssh_session import SSHSession

LogFn = Callable[[str], None]


def _run_configure_script(
    log: LogFn,
    session: SSHSession,
    script_dir: str,
    script_name: str,
    export_branch: str,
    extra_cli: str,
    timeout: int,
    *,
    blank_before: bool,
    extra_env_lines: tuple[str, ...] = (),
) -> None:
    if blank_before:
        log("")
    code, out, err = exec_vpconfigure_script(
        session,
        script_dir,
        script_name,
        export_branch,
        extra_cli,
        timeout,
        extra_env_lines=extra_env_lines,
    )
    status, message, _, line1 = parse_configure_result_line(out)
    log(f"[vpconnect-configure] {script_name}: {line1 or '(пустой stdout)'}")
    if err.strip():
        log(f"[vpconnect-configure] {script_name} stderr:\n{err.rstrip()}")
    if status == "warning":
        log(f"[vpconnect-configure] {script_name}: предупреждение — {message}")
    if _configure_step_failed(status, code):
        abort_configure_on_failure(log, script_name, message, out, err, line1)


def _chmod_remote(
    log: LogFn,
    session: SSHSession,
    path: str,
    timeout: int,
) -> None:
    c, o, e = session.exec_command(f"chmod 600 {shlex.quote(path)}", timeout=timeout)
    if c != 0:
        log(f"Ошибка! chmod {path}: {e.strip() or o}")
        log(INSTALL_ABORTED_MSG)
        raise RuntimeError(INSTALL_ABORTED_MSG)


def need_run_04_connect(config: ProvisionConfig) -> bool:
    """Упрощённый режим — всегда 04. Расширенный — только если задан пароль, порт и/или публичный ключ."""
    if config.auto_setup:
        return True
    return bool(
        config.new_root_password.strip() or config.new_ssh_port is not None or config.new_ssh_public_key.strip()
    )


def _need_run_05(config: ProvisionConfig) -> bool:
    """Упрощённый режим — всегда 05 (домен по внешнему IP).

    Расширенный — домен, его поля, или WG/MT/VPM (нужна переменная VPCONFIGURE_DOMAIN).
    """
    if config.auto_setup:
        return True
    if config.set_domain:
        return True
    if config.domain_client_key.strip():
        return True
    if config.domain and config.domain.strip():
        return True
    if config.use_public_ip:
        return True
    if config.set_wireguard or config.set_mtproxy or config.set_vpmanage:
        return True
    return False


def run_04_connect_steps(
    session: SSHSession,
    home: str,
    configure_dir: str,
    os_branch: str,
    config: ProvisionConfig,
    bundle: ArtifactBundle,
    log: LogFn,
    timeout: int,
) -> None:
    """04_setsystemaccess.sh из configure_dir; вспомогательные файлы — в $HOME.

    Упрощённый режим: всегда пароль (сгенерированный), порт 2222, публичный ключ оператора из артефактов.
    Расширенный: только указанные пароль / порт / один публичный ключ из поля (без ключа оператора).
    """
    tmo = min(timeout, 3600)
    pw_file = f"{home}/.vpconnect_new_root_pw"
    args: list[str] = []

    if config.auto_setup:
        session.upload_bytes(pw_file, (config.new_root_password.strip() + "\n").encode("utf-8"))
        _chmod_remote(log, session, pw_file, 30)
        args.append(f"--new-root-password-file {shlex.quote(pw_file)}")
        args.append(f"--new-ssh-port {int(config.new_ssh_port)}")
        op_pub = f"{home}/vpconnect_operator.pub"
        session.upload_bytes(op_pub, (bundle.public_key_openssh.strip() + "\n").encode("utf-8"))
        _chmod_remote(log, session, op_pub, 30)
        args.append(f"--ssh-public-key-file {shlex.quote(op_pub)}")
        extra = " " + " ".join(args)
        _run_configure_script(
            log,
            session,
            configure_dir,
            "04_setsystemaccess.sh",
            os_branch,
            extra,
            tmo,
            blank_before=True,
        )
        session.exec_command(f"rm -f {shlex.quote(pw_file)}", timeout=30)
        return

    if config.new_root_password.strip():
        session.upload_bytes(pw_file, (config.new_root_password.strip() + "\n").encode("utf-8"))
        _chmod_remote(log, session, pw_file, 30)
        args.append(f"--new-root-password-file {shlex.quote(pw_file)}")
    if config.new_ssh_port is not None:
        args.append(f"--new-ssh-port {int(config.new_ssh_port)}")
    ex = config.new_ssh_public_key.strip()
    if ex:
        exf = f"{home}/vpconnect_extra_ssh.pub"
        session.upload_bytes(exf, (ex + "\n").encode("utf-8"))
        _chmod_remote(log, session, exf, 30)
        args.append(f"--ssh-public-key-file {shlex.quote(exf)}")
    extra = " " + " ".join(args) if args else ""
    _run_configure_script(
        log,
        session,
        configure_dir,
        "04_setsystemaccess.sh",
        os_branch,
        extra,
        tmo,
        blank_before=True,
    )
    if config.new_root_password.strip():
        session.exec_command(f"rm -f {shlex.quote(pw_file)}", timeout=30)


def run_vpconfigure_phases_05_to_08(
    session: SSHSession,
    configure_dir: str,
    os_branch: str,
    config: ProvisionConfig,
    log: LogFn,
    timeout: int,
) -> tuple[str | None, str | None]:
    """05–08 из configure_dir. Перед каждым скриптом — пустая строка в логе."""
    tmo = min(timeout, 3600)
    wg_pub: str | None = None
    mt_secret: str | None = None

    if _need_run_05(config):
        parts: list[str] = ["--persist"]
        dom = (config.domain or "").strip()
        if dom:
            parts.append(f"--domain {shlex.quote(dom)}")
        dkey = config.domain_client_key.strip()
        if dkey and not dom:
            parts.append(f"--domain-client-key {shlex.quote(dkey)}")
        extra = " " + " ".join(parts)
        env = (f"export VPCONFIGURE_DOMAIN_SERVICE_URL={shlex.quote(d.DOMAIN_CLIENT_SERVICE_URL)}",)
        _run_configure_script(
            log,
            session,
            configure_dir,
            "05_setdomain.sh",
            os_branch,
            extra,
            tmo,
            blank_before=True,
            extra_env_lines=env,
        )

    if config.set_wireguard:
        cert = config.wg_client_cert_path.strip() or d.WG_CLIENT_CERT_PATH_DEFAULT
        cdir = config.wg_client_config_path.strip() or d.WG_CLIENT_CONFIG_PATH_DEFAULT
        extra = (
            f" --wg-port {int(config.wg_port)}"
            f" --wg-client-cert-path {shlex.quote(cert)}"
            f" --wg-client-config-path {shlex.quote(cdir)}"
            " --persist"
        )
        _run_configure_script(
            log,
            session,
            configure_dir,
            "06_setwireguard.sh",
            os_branch,
            extra,
            tmo,
            blank_before=True,
        )
        pub_remote = f"{cert.rstrip('/')}/wg_server_public.key"
        try:
            raw = session.download_bytes(pub_remote)
            wg_pub = raw.decode("utf-8", errors="replace").strip()
        except Exception as ex:
            log(f"[vpconnect-configure] Не прочитан публичный ключ WG ({pub_remote}): {ex}")

    if config.set_mtproxy:
        extra = f" --mtproxy-port {int(config.mtproxy_port)} --persist"
        _run_configure_script(
            log,
            session,
            configure_dir,
            "07_setmtproxy.sh",
            os_branch,
            extra,
            tmo,
            blank_before=True,
        )
        sec_path = str(Path("/etc/wireguard") / "mtproxy_secret.txt")
        try:
            sec_raw = session.download_bytes(sec_path)
            mt_secret = sec_raw.decode("utf-8", errors="replace").strip()
        except Exception as ex:
            log(f"[vpconnect-configure] Не прочитан MTProxy secret ({sec_path}): {ex}")

    if config.set_vpmanage:
        vp_args = [f"--http-port {int(config.vpm_http_port)}", "--persist"]
        if config.vpm_password.strip():
            vp_args.append(f"--vpm-password {shlex.quote(config.vpm_password.strip())}")
        extra = " " + " ".join(vp_args)
        _run_configure_script(
            log,
            session,
            configure_dir,
            "08_setvpmanage.sh",
            os_branch,
            extra,
            tmo,
            blank_before=True,
        )

    return wg_pub, mt_secret
