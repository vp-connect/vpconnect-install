"""Тесты разбора stdout vpconnect-configure (пути для SFTP с клиента Windows — POSIX)."""

from __future__ import annotations

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.vpconfigure_provision import (
    _DEFAULT_REMOTE_MTPROXY_SECRET_PATH,
    _mtproxy_secret_path_from_07_stdout,
    _need_run_05,
    _vpm_password_from_08_stdout,
    need_run_04_connect,
)


def test_mtproxy_secret_path_from_07_stdout() -> None:
    out = (
        "result:success; message:OK; mtproxy_port:443; "
        "mtproxy_secret_path:/var/lib/wg/mtproxy_secret.txt; mtproxy_link_path:/tmp/link\n"
    )
    assert _mtproxy_secret_path_from_07_stdout(out) == "/var/lib/wg/mtproxy_secret.txt"


def test_mtproxy_secret_path_from_07_stdout_missing() -> None:
    assert _mtproxy_secret_path_from_07_stdout("result:success; message:only") is None


def test_default_remote_mtproxy_secret_is_posix() -> None:
    assert _DEFAULT_REMOTE_MTPROXY_SECRET_PATH == "/etc/wireguard/mtproxy_secret.txt"
    assert "\\" not in _DEFAULT_REMOTE_MTPROXY_SECRET_PATH


def test_vpm_password_from_08_stdout() -> None:
    out = (
        "result:success; message:OK; vpm_http_port:80; vpm_install_path:/opt/VPManage; "
        "vpm_systemd:vpconnect-manage; mtproxy_secret_path:/a; mtproxy_link_path:/b; "
        "password:Ab3xY9mK2q\n"
    )
    assert _vpm_password_from_08_stdout(out) == "Ab3xY9mK2q"


def test_vpm_password_from_08_stdout_missing() -> None:
    assert _vpm_password_from_08_stdout("result:success; message:only") is None


def _pc(**kw: object) -> ProvisionConfig:
    base = dict(
        host="h",
        port=22,
        root_password="p",
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    base.update(kw)
    return ProvisionConfig(**base)  # type: ignore[arg-type]


def test_need_run_04_auto_setup_true() -> None:
    assert need_run_04_connect(_pc(auto_setup=True)) is True


def test_need_run_04_manual_only_when_connect_tuning() -> None:
    assert need_run_04_connect(_pc(auto_setup=False)) is False
    assert need_run_04_connect(_pc(auto_setup=False, new_root_password="x")) is True
    assert need_run_04_connect(_pc(auto_setup=False, new_ssh_port=2222)) is True
    assert need_run_04_connect(_pc(auto_setup=False, new_ssh_public_key="ssh-rsa A")) is True
    assert need_run_04_connect(_pc(auto_setup=False, enable_firewall=True)) is True


def test_need_run_05_matrix() -> None:
    assert _need_run_05(_pc(auto_setup=True)) is True
    assert _need_run_05(_pc(auto_setup=False, set_domain=True)) is True
    assert _need_run_05(_pc(auto_setup=False, domain="d.example")) is True
    assert _need_run_05(_pc(auto_setup=False, use_public_ip=True)) is True
    assert _need_run_05(_pc(auto_setup=False, set_wireguard=True)) is True
    assert _need_run_05(_pc(auto_setup=False, set_mtproxy=True)) is True
    assert _need_run_05(_pc(auto_setup=False, set_vpmanage=True)) is True
    assert _need_run_05(_pc(auto_setup=False)) is False
