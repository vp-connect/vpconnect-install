"""Полный прогон runner.run с подменой SSH и bootstrap (без сети)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.runner import run


def _minimal_run_config(**kw: object) -> ProvisionConfig:
    defaults = dict(
        host="10.0.0.1",
        port=22,
        root_password="pw",
        auto_setup=True,
        set_wireguard=True,
        set_mtproxy=True,
        set_vpmanage=True,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
        ssh_connect_timeout=5,
        reboot_wait_timeout=2,
        ssh_poll_interval=1,
        command_timeout=60,
    )
    defaults.update(kw)
    return ProvisionConfig(**defaults)  # type: ignore[arg-type]


@patch("vpconnect_install.runner._poll_ssh_after_reboot")
@patch("vpconnect_install.runner._request_reboot")
@patch("vpconnect_install.runner.run_vpconfigure_phases_05_to_08")
@patch("vpconnect_install.runner._maybe_reconnect_session", side_effect=lambda s, _c, _l: s)
@patch("vpconnect_install.runner.run_04_connect_steps")
@patch("vpconnect_install.runner.need_run_04_connect", return_value=True)
@patch("vpconnect_install.runner.run_vpconnect_configure_bootstrap")
@patch("vpconnect_install.runner.SSHSession")
def test_run_full_pipeline_mocked(
    mock_ssh_cls: MagicMock,
    mock_bootstrap: MagicMock,
    _need04: MagicMock,
    mock_04: MagicMock,
    mock_maybe: MagicMock,
    mock_05_08: MagicMock,
    mock_reboot: MagicMock,
    mock_poll_reboot: MagicMock,
    tmp_path: Path,
) -> None:
    session = MagicMock()
    session.auth_method = "password"
    session.exec_command.return_value = (0, "203.0.113.10\n", "")
    mock_ssh_cls.return_value = session
    mock_bootstrap.return_value = ("/root", "debian", "/root/vpconnect-configure")

    cfg = _minimal_run_config()
    base = tmp_path / "artifacts"
    base.mkdir()
    logs: list[str] = []

    out = run(cfg, log=logs.append, artifacts_base=base)

    assert out.is_dir()
    session.connect.assert_called()
    mock_bootstrap.assert_called_once()
    mock_04.assert_called_once()
    mock_05_08.assert_called_once()
    mock_reboot.assert_called_once()
    mock_poll_reboot.assert_called_once()
    session.close.assert_called()


@patch("vpconnect_install.runner._poll_ssh_after_reboot")
@patch("vpconnect_install.runner._request_reboot")
@patch("vpconnect_install.runner.run_vpconfigure_phases_05_to_08")
@patch("vpconnect_install.runner._maybe_reconnect_session", side_effect=lambda s, _c, _l: s)
@patch("vpconnect_install.runner.run_04_connect_steps")
@patch("vpconnect_install.runner.need_run_04_connect", return_value=False)
@patch("vpconnect_install.runner.run_vpconnect_configure_bootstrap")
@patch("vpconnect_install.runner.SSHSession")
def test_run_skips_04_when_not_needed(
    mock_ssh_cls: MagicMock,
    mock_bootstrap: MagicMock,
    _need04: MagicMock,
    mock_04: MagicMock,
    mock_maybe: MagicMock,
    mock_05_08: MagicMock,
    mock_reboot: MagicMock,
    mock_poll_reboot: MagicMock,
    tmp_path: Path,
) -> None:
    session = MagicMock()
    session.auth_method = "private_key"
    session.exec_command.return_value = (0, "1.2.3.4", "")
    mock_ssh_cls.return_value = session
    mock_bootstrap.return_value = ("/root", "centos", "/cfg")

    cfg = _minimal_run_config()
    cfg.auto_setup = False
    cfg.new_root_password = ""
    cfg.new_ssh_port = None
    cfg.new_ssh_public_key = ""
    cfg.enable_firewall = False
    cfg.set_wireguard = False
    cfg.set_mtproxy = False
    cfg.set_vpmanage = False
    cfg.domain = "d.example"
    base = tmp_path / "a"
    base.mkdir()

    run(cfg, log=lambda _m: None, artifacts_base=base)

    mock_04.assert_not_called()
    mock_05_08.assert_called_once()


@patch("vpconnect_install.runner._poll_ssh_after_reboot")
@patch("vpconnect_install.runner._request_reboot")
@patch("vpconnect_install.runner.run_vpconfigure_phases_05_to_08")
@patch("vpconnect_install.runner._maybe_reconnect_session")
@patch("vpconnect_install.runner.need_run_04_connect", return_value=True)
@patch("vpconnect_install.runner.run_04_connect_steps")
@patch("vpconnect_install.runner.run_vpconnect_configure_bootstrap")
@patch("vpconnect_install.runner.SSHSession")
def test_run_maybe_reconnect_replaces_session(
    mock_ssh_cls: MagicMock,
    mock_bootstrap: MagicMock,
    mock_04: MagicMock,
    _need04: MagicMock,
    mock_maybe: MagicMock,
    mock_05_08: MagicMock,
    mock_reboot: MagicMock,
    mock_poll_reboot: MagicMock,
    tmp_path: Path,
) -> None:
    s1 = MagicMock()
    s1.auth_method = "password"
    s1.exec_command.return_value = (0, "9.9.9.9", "")
    s2 = MagicMock()
    s2.auth_method = "password"
    mock_ssh_cls.return_value = s1
    mock_maybe.side_effect = lambda _s, _c, _l: s2
    mock_bootstrap.return_value = ("/root", "debian", "/c")

    cfg = _minimal_run_config()
    base = tmp_path / "b"
    base.mkdir()
    run(cfg, log=lambda _m: None, artifacts_base=base)

    mock_05_08.assert_called_once()
    cargs, _ = mock_05_08.call_args
    assert cargs[0] is s2
