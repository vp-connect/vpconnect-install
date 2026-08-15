"""Юнит-тесты предпроверки портов на сервере (мок SSH exec_command)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shared import defaults as d
from config import ProvisionConfig
from server.remote_port_precheck import (
    MTPROXY_INTERNAL_TCP_PORT,
    PortCheck,
    _is_expected_reinstall_owner,
    assert_remote_listen_ports_free,
    required_listen_port_checks,
)


def test_required_listen_port_checks_empty_when_no_services() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=False,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    assert required_listen_port_checks(cfg) == []


def test_required_listen_port_checks_auto_setup_new_ssh() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=True,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    checks = required_listen_port_checks(cfg)
    assert len(checks) == 1
    assert checks[0].proto == "tcp"
    assert checks[0].port == 2222


def test_required_listen_port_checks_skips_current_ssh_port() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=2222,
        root_password="x",
        auto_setup=True,
        new_ssh_port=2222,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    assert required_listen_port_checks(cfg) == []


def test_required_listen_port_checks_mtproxy_includes_internal_8888() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=False,
        set_mtproxy=True,
        mtproxy_port=8443,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    specs = {(c.proto, c.port) for c in required_listen_port_checks(cfg)}
    assert ("tcp", 8443) in specs
    assert ("tcp", MTPROXY_INTERNAL_TCP_PORT) in specs


def test_required_listen_port_checks_mtproxy_dedupes_8888() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=False,
        set_mtproxy=True,
        mtproxy_port=MTPROXY_INTERNAL_TCP_PORT,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    ports = [c.port for c in required_listen_port_checks(cfg) if c.proto == "tcp"]
    assert ports.count(MTPROXY_INTERNAL_TCP_PORT) == 1


def test_assert_remote_listen_ports_free_noop_when_empty() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=False,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    session = MagicMock()
    assert_remote_listen_ports_free(session, cfg, lambda _m: None, 60)
    session.exec_command.assert_not_called()


def test_assert_remote_listen_ports_free_success() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=True,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    session = MagicMock()
    session.exec_command.return_value = (0, "", "")
    assert_remote_listen_ports_free(session, cfg, lambda _m: None, 60)
    session.exec_command.assert_called_once()
    cmd = session.exec_command.call_args[0][0]
    assert "sport = :" in cmd
    assert "2222" in cmd


def test_is_expected_reinstall_owner_marker_in_details() -> None:
    c = PortCheck(proto="tcp", port=22, purpose="ssh", service="ssh")
    assert _is_expected_reinstall_owner(c, "x OWNER:ssh y") is True


def test_is_expected_reinstall_owner_empty_details_false() -> None:
    c = PortCheck(proto="tcp", port=22, purpose="ssh", service="ssh")
    assert _is_expected_reinstall_owner(c, "   \n") is False


def test_is_expected_reinstall_owner_regex_mtproxy() -> None:
    c = PortCheck(proto="tcp", port=25, purpose="mt", service="mtproxy")
    assert _is_expected_reinstall_owner(c, "LISTEN mtproto-proxy") is True


def test_assert_remote_listen_ports_free_generic_failure_no_busy_lines() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=True,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    session = MagicMock()
    session.exec_command.return_value = (9, "some stdout", "stderr msg")
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        assert_remote_listen_ports_free(session, cfg, lambda _m: None, 60)


def test_assert_remote_listen_ports_free_busy_raises() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=True,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    session = MagicMock()
    session.exec_command.return_value = (1, "BUSY:tcp:2222|nc 111 root\n", "")
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        assert_remote_listen_ports_free(session, cfg, logs.append, 60)
    assert any("2222" in m for m in logs)


def test_assert_remote_listen_ports_free_busy_our_service_allows_reinstall() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=True,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    session = MagicMock()
    session.exec_command.return_value = (1, "BUSY:tcp:2222|users:((\"sshd\",pid=101,fd=3));\n", "")
    logs: list[str] = []
    assert_remote_listen_ports_free(session, cfg, logs.append, 60)
    assert any("повторная установка" in m for m in logs)


def test_assert_remote_listen_ports_free_missing_tool_raises() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=True,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    cfg.apply_auto_setup()
    session = MagicMock()
    session.exec_command.return_value = (
        2,
        "",
        "Не найдены команды ss или sockstat (FreeBSD) для проверки портов.\n",
    )
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        assert_remote_listen_ports_free(session, cfg, lambda _m: None, 60)


def test_assert_remote_listen_ports_free_vpserver_owner_marker_allows_reinstall() -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=False,
        set_vpserver=True,
        vp_port=4443,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
    )
    session = MagicMock()
    session.exec_command.return_value = (
        1,
        "BUSY:udp:4443|OWNER:vpserver|udp UNCONN 0 0 0.0.0.0:4443 0.0.0.0:*;\n",
        "",
    )
    logs: list[str] = []
    assert_remote_listen_ports_free(session, cfg, logs.append, 60)
    assert any("повторная установка" in m for m in logs)


@pytest.mark.parametrize(
    ("cfg_kwargs", "busy_line"),
    [
        (
            {"set_mtproxy": True, "mtproxy_port": 25},
            "BUSY:tcp:25|OWNER:mtproxy|tcp LISTEN 0 4096 0.0.0.0:25 users:((\"mtproto-proxy\",pid=513,fd=3));\n",
        ),
        (
            {"set_vpmanage": True, "vpm_http_port": 80},
            "BUSY:tcp:80|OWNER:vpmanage|tcp LISTEN 0 2048 0.0.0.0:80 users:((\"gunicorn\",pid=584,fd=3));\n",
        ),
    ],
)
def test_assert_remote_listen_ports_free_owner_markers_allow_reinstall(
    cfg_kwargs: dict[str, object],
    busy_line: str,
) -> None:
    cfg = ProvisionConfig(
        host="h",
        port=22,
        root_password="x",
        auto_setup=False,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
        **cfg_kwargs,
    )
    session = MagicMock()
    session.exec_command.return_value = (1, busy_line, "")
    logs: list[str] = []
    assert_remote_listen_ports_free(session, cfg, logs.append, 60)
    assert any("повторная установка" in m for m in logs)
