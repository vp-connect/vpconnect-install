"""Тесты _run_configure_script с подменой exec_vpconfigure_script."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vpconnect_install.vpconfigure_provision import _run_configure_script


def test_run_configure_script_success() -> None:
    session = MagicMock()
    log: list[str] = []
    out = "result:success; message:OK\n"
    with patch(
        "vpconnect_install.vpconfigure_provision.exec_vpconfigure_script",
        return_value=(0, out, ""),
    ):
        got = _run_configure_script(
            log.append, session, "/d", "06_x.sh", "debian", "", 30, blank_before=False
        )
    assert got == out
    assert any("06_x.sh" in m for m in log)


def test_run_configure_script_warning_does_not_abort() -> None:
    session = MagicMock()
    log: list[str] = []
    out = "result:warning; message:careful\n"
    with patch(
        "vpconnect_install.vpconfigure_provision.exec_vpconfigure_script",
        return_value=(0, out, ""),
    ):
        got = _run_configure_script(
            log.append, session, "/d", "05_x.sh", "debian", "", 30, blank_before=False
        )
    assert got == out
    assert any("предупреждение" in m for m in log)


def test_run_configure_script_aborts_on_error() -> None:
    session = MagicMock()
    log: list[str] = []
    out = "result:error; message:fail\n"
    with patch(
        "vpconnect_install.vpconfigure_provision.exec_vpconfigure_script",
        return_value=(1, out, "e"),
    ):
        with pytest.raises(RuntimeError, match="Установка прекращена"):
            _run_configure_script(
                log.append, session, "/d", "bad.sh", "debian", "", 30, blank_before=True
            )
    assert log[0] == ""
