"""
Разбор аргументов командной строки и сборка :class:`~vpconnect_install.config.ProvisionConfig`.

Точка входа CLI — :func:`main` (вызывается из :mod:`vpconnect_install.__main__`).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.runner import run

_CLI_EPILOG = (
    "Supported: Python 3.10+ on Windows, Linux, or macOS. "
    "Target server: three OS families from vpconnect-configure — "
    "debian (Debian/Ubuntu, apt), centos (RHEL/Alma/Rocky/Fedora/AL2023…), freebsd. "
    "Exact OS versions: see vpconnect-configure README."
)


def _read_file(path: str) -> str:
    """Прочитать текстовый файл и вернуть содержимое без пробелов по краям."""
    return Path(path).read_text(encoding="utf-8").strip()


def _secret(cli_value: str | None, env_name: str, file_arg: str | None) -> str:
    """Секрет: аргумент CLI, иначе файл ``file_arg``, иначе переменная окружения ``env_name``."""
    if cli_value:
        return cli_value
    if file_arg:
        return _read_file(file_arg)
    return os.environ.get(env_name, "").strip()


def _feature_flags_from_ns(ns: argparse.Namespace) -> tuple[bool, bool, bool]:
    """Флаги WireGuard / MTProxy / VPManage с учётом ``--auto-setup`` и ``--no-*`` по умолчанию."""
    wg, mt, vpm = ns.set_wireguard, ns.set_mtproxy, ns.set_vpmanage
    if not ns.auto_setup:
        return (
            False if wg is None else bool(wg),
            False if mt is None else bool(mt),
            False if vpm is None else bool(vpm),
        )
    return (
        True if wg is None else bool(wg),
        True if mt is None else bool(mt),
        True if vpm is None else bool(vpm),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Парсер аргументов для ``python -m vpconnect_install`` (без подкоманды ``gui``)."""
    p = argparse.ArgumentParser(
        prog="python -m vpconnect_install",
        description="Provision server over SSH via vpconnect-configure (WireGuard, MTProxy, VPManage).",
        epilog=_CLI_EPILOG,
    )
    p.add_argument("--host", required=True, help="Server IP or hostname (required)")
    p.add_argument(
        "--port",
        type=int,
        default=22,
        help="SSH port (required; default 22)",
    )
    p.add_argument("--root-password", default=None, help="Root password (env ROOT_PASSWORD)")
    p.add_argument("--root-password-file", default=None, help="File with root password")
    p.add_argument(
        "--root-private-key",
        default="",
        help="Path to SSH private key (OpenSSH / PEM)",
    )
    p.add_argument(
        "--root-private-key-passphrase",
        default=None,
        help="Passphrase for private key (env ROOT_KEY_PASSPHRASE)",
    )
    p.add_argument(
        "--root-private-key-passphrase-file",
        default=None,
        help="File with key passphrase",
    )
    p.add_argument(
        "--auto-setup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use defaults and auto-generate secrets (default: true)",
    )
    p.add_argument(
        "--new-root-password",
        default=None,
        help="New root password; omit to skip (env NEW_ROOT_PASSWORD)",
    )
    p.add_argument("--new-root-password-file", default=None)
    p.add_argument(
        "--new-ssh-port",
        type=int,
        default=None,
        help="New SSH port; omit to leave unchanged",
    )
    p.add_argument(
        "--enable-firewall",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable ufw firewall in 04_setsystemaccess (default: with --auto-setup, else off)",
    )
    p.add_argument("--new-ssh-public-key", default=None, help="Extra OpenSSH public line for root")
    p.add_argument("--new-ssh-public-key-file", default=None)
    p.add_argument("--domain", default=None, help="Manual FQDN for URLs (APP_DOMAIN)")
    p.add_argument(
        "--use-public-ip",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When no domain: detect public IP on server (not needed with --auto-setup)",
    )
    p.add_argument(
        "--vpconfigure-repo-url",
        default=d.VPCONFIGURE_REPO_URL_DEFAULT,
        help="GitHub repo vpconnect-configure (scripts 00–03, raw branch is always main)",
    )
    p.add_argument(
        "--set-wireguard",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Install WireGuard (when not using --auto-setup)",
    )
    p.add_argument(
        "--set-mtproxy",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    p.add_argument(
        "--set-vpmanage",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    p.add_argument("--wg-port", type=int, default=d.WG_PORT_DEFAULT)
    p.add_argument("--wg-client-cert-path", default=d.WG_CLIENT_CERT_PATH_DEFAULT)
    p.add_argument("--wg-client-config-path", default=d.WG_CLIENT_CONFIG_PATH_DEFAULT)
    p.add_argument("--mtproxy-port", type=int, default=d.MTPROXY_PORT_DEFAULT)
    p.add_argument("--vpm-http-port", type=int, default=d.VPM_HTTP_PORT_DEFAULT)
    p.add_argument(
        "--vpm-password",
        default=None,
        help="VPManage admin password (env VPM_PASSWORD); if omitted, generated on server (08)",
    )
    p.add_argument("--vpm-password-file", default=None)
    p.add_argument("--ssh-connect-timeout", type=int, default=d.SSH_CONNECT_TIMEOUT)
    p.add_argument("--command-timeout", type=int, default=d.COMMAND_TIMEOUT)
    p.add_argument("--reboot-wait-timeout", type=int, default=d.REBOOT_WAIT_TIMEOUT)
    p.add_argument("--ssh-poll-interval", type=int, default=d.SSH_POLL_INTERVAL)
    p.add_argument(
        "--artifacts-dir",
        default=None,
        help="Base directory for provision-artifacts",
    )
    return p


def config_from_args(ns: argparse.Namespace) -> ProvisionConfig:
    """Собрать :class:`~vpconnect_install.config.ProvisionConfig` из ``parse_args``."""
    root_pw = _secret(ns.root_password, "ROOT_PASSWORD", ns.root_password_file)
    key_pp = _secret(
        ns.root_private_key_passphrase,
        "ROOT_KEY_PASSPHRASE",
        ns.root_private_key_passphrase_file,
    )
    new_root = _secret(ns.new_root_password, "NEW_ROOT_PASSWORD", ns.new_root_password_file)
    vpm_pw = _secret(ns.vpm_password, "VPM_PASSWORD", ns.vpm_password_file)
    extra_pub = ns.new_ssh_public_key or ""
    if ns.new_ssh_public_key_file:
        extra_pub = _read_file(ns.new_ssh_public_key_file)

    set_wg, set_mt, set_vpm = _feature_flags_from_ns(ns)

    domain = ns.domain.strip() if ns.domain else None

    enable_fw: bool
    if ns.enable_firewall is None:
        enable_fw = bool(ns.auto_setup)
    else:
        enable_fw = bool(ns.enable_firewall)

    return ProvisionConfig(
        host=ns.host,
        port=ns.port,
        root_password=root_pw,
        root_private_key=(ns.root_private_key or "").strip(),
        root_private_key_passphrase=key_pp,
        auto_setup=ns.auto_setup,
        set_new_connect=False,
        new_root_password=new_root,
        new_ssh_port=ns.new_ssh_port,
        new_ssh_public_key=extra_pub,
        enable_firewall=enable_fw,
        set_domain=False,
        domain=domain,
        use_public_ip=bool(ns.use_public_ip),
        set_wireguard=bool(set_wg),
        set_mtproxy=bool(set_mt),
        set_vpmanage=bool(set_vpm),
        wg_port=ns.wg_port,
        wg_client_cert_path=ns.wg_client_cert_path,
        wg_client_config_path=ns.wg_client_config_path,
        mtproxy_port=ns.mtproxy_port,
        vpm_http_port=ns.vpm_http_port,
        vpm_password=vpm_pw,
        vpconfigure_repo_url=(ns.vpconfigure_repo_url or "").strip() or d.VPCONFIGURE_REPO_URL_DEFAULT,
        ssh_connect_timeout=ns.ssh_connect_timeout,
        command_timeout=ns.command_timeout,
        reboot_wait_timeout=ns.reboot_wait_timeout,
        ssh_poll_interval=ns.ssh_poll_interval,
    )


def main(argv: list[str] | None = None) -> int:
    """Запустить один прогон установки; вернуть ``0`` при успехе, ``1`` при исключении."""
    args = build_arg_parser().parse_args(argv)
    cfg = config_from_args(args)
    base = Path(args.artifacts_dir).resolve() if args.artifacts_dir else None

    def log(msg: str) -> None:
        print(msg, flush=True)

    try:
        run(cfg, log=log, artifacts_base=base)
    except Exception as e:
        log(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
