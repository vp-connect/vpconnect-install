"""
Модель параметров одного прогона установки (CLI и GUI).

Валидация в :meth:`ProvisionConfig.validate`, автозаполнение в :meth:`ProvisionConfig.apply_auto_setup`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from pathlib import Path

from vpconnect_install import defaults as d
from vpconnect_install.remote_scripts_fetch import parse_github_repo_url


def _port_ok(p: int) -> bool:
    return 1 <= p <= 65535


@dataclass
class ProvisionConfig:
    """All parameters for one provisioning run (CLI and GUI)."""

    host: str
    port: int = 22
    root_password: str = ""
    root_private_key: str = ""
    root_private_key_passphrase: str = ""

    auto_setup: bool = True

    # GUI only: enable fields for "connection tuning" group
    set_new_connect: bool = False
    new_root_password: str = ""
    new_ssh_port: int | None = None
    new_ssh_public_key: str = ""
    enable_firewall: bool = False

    # GUI: master toggle for domain section
    set_domain: bool = False
    domain: str | None = None
    domain_client_key: str = ""
    # CLI: detect public IP on server (like former --request-domain) when no domain/key
    use_public_ip: bool = False

    set_wireguard: bool = False
    wg_port: int = d.WG_PORT_DEFAULT
    wg_client_cert_path: str = d.WG_CLIENT_CERT_PATH_DEFAULT
    wg_client_config_path: str = d.WG_CLIENT_CONFIG_PATH_DEFAULT

    set_mtproxy: bool = False
    mtproxy_port: int = d.MTPROXY_PORT_DEFAULT

    set_vpmanage: bool = False
    vpm_http_port: int = d.VPM_HTTP_PORT_DEFAULT
    vpm_password: str = ""

    git_url: str = d.GIT_URL
    git_branch: str = d.GIT_BRANCH
    install_path: str = d.INSTALL_PATH
    systemd_service: str = d.SYSTEMD_SERVICE_VPMANAGE

    # Скрипты 00–03 с GitHub → домашний каталог на сервере, затем по очереди
    vpconfigure_repo_url: str = d.VPCONFIGURE_REPO_URL_DEFAULT

    ssh_connect_timeout: int = d.SSH_CONNECT_TIMEOUT
    command_timeout: int = d.COMMAND_TIMEOUT
    reboot_wait_timeout: int = d.REBOOT_WAIT_TIMEOUT
    ssh_poll_interval: int = d.SSH_POLL_INTERVAL

    effective_domain_or_ip: str | None = field(default=None, repr=False)

    def apply_auto_setup(self) -> None:
        """Fill domain mode and generated secrets when auto_setup is True (flags come from CLI/GUI)."""
        if not self.auto_setup:
            return
        self.domain = None
        # В auto_setup домен обычно определяется по внешнему IP.
        # Но если пользователь задал ключ сервиса домена — не затираем его (05_setdomain сможет получить FQDN).
        self.domain_client_key = self.domain_client_key.strip()
        # Упрощённый режим: всегда новый пароль, порт 2222, только ключ оператора из артефактов (не поле extra).
        if not self.new_root_password.strip():
            self.new_root_password = secrets.token_urlsafe(d.SECRET_TOKEN_BYTES)
        if self.new_ssh_port is None:
            self.new_ssh_port = 2222
        self.new_ssh_public_key = ""
        if self.set_vpmanage and not self.vpm_password.strip():
            self.vpm_password = secrets.token_urlsafe(d.SECRET_TOKEN_BYTES)

    def validate(self) -> None:
        _validate_required_ports(self)
        _validate_ssh_credentials(self)
        _validate_vpconfigure_repo(self)
        if self.set_vpmanage and not self.vpm_password.strip():
            raise ValueError("vpm_password is required when set_vpmanage (run apply_auto_setup or set a password)")
        _validate_domain_manual(self)


def _validate_required_ports(cfg: ProvisionConfig) -> None:
    if not cfg.host.strip():
        raise ValueError("host is required")
    if not _port_ok(cfg.port):
        raise ValueError(f"SSH port is required and must be 1–65535 (got {cfg.port})")
    if cfg.new_ssh_port is not None and not _port_ok(cfg.new_ssh_port):
        raise ValueError(f"invalid new_ssh_port: {cfg.new_ssh_port}")
    for name, p in (
        ("wg_port", cfg.wg_port),
        ("mtproxy_port", cfg.mtproxy_port),
        ("vpm_http_port", cfg.vpm_http_port),
    ):
        if not _port_ok(p):
            raise ValueError(f"invalid {name}: {p}")


def _validate_ssh_credentials(cfg: ProvisionConfig) -> None:
    key_path = cfg.root_private_key.strip()
    has_key = bool(key_path and Path(key_path).is_file())
    has_pw = bool(cfg.root_password)
    if not has_key and not has_pw:
        raise ValueError("Provide root_password and/or a valid root_private_key file path")


def _validate_vpconfigure_repo(cfg: ProvisionConfig) -> None:
    u = (cfg.vpconfigure_repo_url or "").strip()
    if not u:
        raise ValueError("vpconfigure_repo_url is required")
    try:
        parse_github_repo_url(u)
    except ValueError as e:
        raise ValueError(f"vpconfigure_repo_url: {e}") from e


def _validate_domain_manual(cfg: ProvisionConfig) -> None:
    if cfg.auto_setup:
        return
    if cfg.domain is not None and not cfg.domain.strip():
        raise ValueError("domain must be non-empty when specified")
