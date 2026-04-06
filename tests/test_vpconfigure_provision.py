"""Тесты разбора stdout vpconnect-configure (пути для SFTP с клиента Windows — POSIX)."""

from __future__ import annotations

from vpconnect_install.vpconfigure_provision import (
    _DEFAULT_REMOTE_MTPROXY_SECRET_PATH,
    _mtproxy_secret_path_from_07_stdout,
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
