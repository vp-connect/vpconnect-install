"""Полный run_vpconnect_configure_bootstrap с моками HTTP и SSH."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vpconnect_install import defaults as d
from vpconnect_install.config import ProvisionConfig
from vpconnect_install.configure_bootstrap import run_vpconnect_configure_bootstrap


def _exec_bootstrap(cmd: str, timeout: object = None) -> tuple[int, str, str]:
    if "printf %s" in cmd and "HOME" in cmd:
        return (0, "/root\n", "")
    if cmd.startswith("chmod +x"):
        return (0, "", "")
    if "bash -lc" not in cmd:
        return (99, "", f"unexpected cmd head: {cmd[:40]}")
    if "00_bashinstall.sh" in cmd:
        return (0, "result:success; message:ok\n", "")
    if "01_getosversion.sh" in cmd:
        return (0, "result:success; message:ok; branch:debian\n", "")
    if "02_gitinstall.sh" in cmd:
        return (0, "result:success; message:git ok\n", "")
    if "03_getconfigure.sh" in cmd:
        return (
            0,
            "result:success; message:clone; path:/root/vpconnect-configure; branch:debian\n",
            "",
        )
    if "test -d" in cmd and "04_setsystemaccess.sh" in cmd:
        return (0, "", "")
    return (1, "", f"unhandled: {cmd[:120]}")


@patch("vpconnect_install.configure_bootstrap.requests.get")
def test_run_vpconnect_configure_bootstrap_happy_path(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.content = b"#!/usr/bin/env bash\n#stub\n"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    session = MagicMock()
    session.exec_command.side_effect = _exec_bootstrap

    cfg = ProvisionConfig(
        host="10.0.0.1",
        port=22,
        root_password="x",
        auto_setup=False,
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
        command_timeout=120,
    )
    logs: list[str] = []
    home, os_branch, configure_dir = run_vpconnect_configure_bootstrap(session, cfg, logs.append)

    assert home == "/root"
    assert os_branch == "debian"
    assert configure_dir == "/root/vpconnect-configure"
    assert session.upload_bytes.call_count == 4
    assert any("завершены успешно" in m for m in logs)


@patch("vpconnect_install.configure_bootstrap.requests.get")
@patch("vpconnect_install.configure_bootstrap._chmod_plus_x_remote", side_effect=ValueError("chmod boom"))
def test_bootstrap_chmod_unexpected_exception_aborts(mock_chmod: MagicMock, mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.content = b"#!/bin/bash\n"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp
    session = MagicMock()
    session.exec_command.return_value = (0, "/root\n", "")
    cfg = ProvisionConfig(
        host="10.0.0.1",
        port=22,
        root_password="x",
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
        command_timeout=120,
    )
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        run_vpconnect_configure_bootstrap(session, cfg, lambda _m: None)


@patch("vpconnect_install.configure_bootstrap.requests.get")
def test_fetch_script_network_error_aborts(mock_get: MagicMock) -> None:
    import requests

    mock_get.side_effect = requests.RequestException("offline")
    session = MagicMock()
    session.exec_command.return_value = (0, "/root\n", "")
    cfg = ProvisionConfig(
        host="10.0.0.1",
        port=22,
        root_password="x",
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
        command_timeout=120,
    )
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        run_vpconnect_configure_bootstrap(session, cfg, lambda _m: None)


def test_remote_home_empty_stdout_raises() -> None:
    from vpconnect_install.configure_bootstrap import _remote_home

    session = MagicMock()
    session.exec_command.return_value = (0, "\n", "")
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        _remote_home(session, logs.append, 10)


def test_remote_home_failure() -> None:
    from vpconnect_install.configure_bootstrap import _remote_home

    session = MagicMock()
    session.exec_command.return_value = (1, "", "no home")
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        _remote_home(session, logs.append, 10)


@patch("vpconnect_install.configure_bootstrap.requests.get")
def test_bootstrap_script_step_failure_aborts(mock_get: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.content = b"#!/bin/bash\n"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    def exec_command(cmd: str, timeout: object = None) -> tuple[int, str, str]:
        if "printf %s" in cmd and "HOME" in cmd:
            return (0, "/root\n", "")
        if cmd.startswith("chmod +x"):
            return (0, "", "")
        if "00_bashinstall.sh" in cmd:
            return (0, "result:error; message:bad\n", "")
        return (1, "", "unexpected")

    session = MagicMock()
    session.exec_command.side_effect = exec_command
    cfg = ProvisionConfig(
        host="10.0.0.1",
        port=22,
        root_password="x",
        vpconfigure_repo_url=d.VPCONFIGURE_REPO_URL_DEFAULT,
        command_timeout=120,
    )
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        run_vpconnect_configure_bootstrap(session, cfg, lambda _m: None)


def test_chmod_plus_x_remote_raises() -> None:
    from vpconnect_install.configure_bootstrap import _chmod_plus_x_remote

    session = MagicMock()
    session.exec_command.return_value = (1, "", "chmod failed")
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        _chmod_plus_x_remote(session, logs.append, "/r/script.sh", "s.sh")
