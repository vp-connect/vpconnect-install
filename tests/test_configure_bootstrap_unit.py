"""Доп. тесты configure_bootstrap (без сети и полного bootstrap)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vpconnect_install.configure_bootstrap import (
    INSTALL_ABORTED_MSG,
    abort_configure_on_failure,
    exec_vpconfigure_script,
    parse_configure_result_line,
    resolve_configure_install_dir,
    verify_configure_scripts_dir,
    _bootstrap_export_branch,
    _configure_step_failed,
    _parse_configure_result_segments,
    _stdout_lines_before_marked_line,
)


def test_configure_step_failed_matrix() -> None:
    assert _configure_step_failed("error", 0) is True
    assert _configure_step_failed("unknown", 0) is True
    assert _configure_step_failed("success", 1) is True
    assert _configure_step_failed("success", 0) is False
    assert _configure_step_failed("warning", 0) is False


def test_stdout_lines_before_marked_line() -> None:
    full = "line1\nline2\nresult:success; message:x\n"
    assert _stdout_lines_before_marked_line(full, "result:success; message:x") == "line1\nline2"
    assert _stdout_lines_before_marked_line("", "x") == ""
    assert _stdout_lines_before_marked_line("only", "only") == ""


def test_parse_configure_result_segments_skips_empty_between_semicolons() -> None:
    st, msg, br = _parse_configure_result_segments("result:ok;;message:hi; branch:dev")
    assert st == "ok"
    assert msg == "hi"
    assert br == "dev"


def test_parse_configure_result_line_finds_last_result_among_noise() -> None:
    out = "apt noise\nresult:old; message:x\nresult:ok; message:done\n"
    st, msg, br, line1 = parse_configure_result_line(out)
    assert st == "ok"
    assert msg == "done"
    assert line1.startswith("result:ok")


def test_abort_configure_on_failure_logs_and_raises() -> None:
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        abort_configure_on_failure(
            logs.append,
            "01.sh",
            "bad",
            "noise\nresult:error; message:bad",
            "stderr here",
            "result:error; message:bad",
        )
    assert INSTALL_ABORTED_MSG in "".join(logs)
    assert any("доп. вывод" in m for m in logs)


def test_abort_configure_on_failure_non_result_line_logs_rest_of_stdout() -> None:
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        abort_configure_on_failure(
            logs.append,
            "s.sh",
            "",
            "first line\nsecond line\n",
            "",
            "not a result line",
        )
    assert any("доп. вывод stdout" in m and "second line" in m for m in logs)


def test_bootstrap_export_branch_requires_os_branch_from_01() -> None:
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        _bootstrap_export_branch(2, None, logs.append)


def test_exec_vpconfigure_script_builds_bash_lc() -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "ok", "")
    exec_vpconfigure_script(session, "/home/u", "00_x.sh", "debian", " --a 1", 60)
    session.exec_command.assert_called_once()
    cmd = session.exec_command.call_args[0][0]
    assert cmd.startswith("bash -lc ")
    assert "00_x.sh" in cmd
    assert "VPCONFIGURE_GIT_BRANCH" in cmd


def test_exec_vpconfigure_script_no_export_branch() -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "", "")
    exec_vpconfigure_script(session, "/h", "s.sh", None, "", 10, extra_env_lines=("export FOO=1",))
    cmd = session.exec_command.call_args[0][0]
    assert "FOO=1" in cmd
    assert "VPCONFIGURE_GIT_BRANCH" not in cmd


def test_resolve_configure_install_dir_from_03_path() -> None:
    session = MagicMock()
    out = "result:success; message:OK; path:/opt/vpc; branch:debian\n"
    log: list[str] = []
    d = resolve_configure_install_dir(session, "/root", log.append, out, 30)
    assert d == "/opt/vpc"
    session.exec_command.assert_not_called()


def test_resolve_configure_install_dir_from_remote_cmd() -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "/var/vp\n", "")
    log: list[str] = []
    d = resolve_configure_install_dir(session, "/root", log.append, "no path line", 30)
    assert d == "/var/vp"


def test_resolve_configure_install_dir_fallback() -> None:
    session = MagicMock()
    session.exec_command.return_value = (1, "", "err")
    log: list[str] = []
    d = resolve_configure_install_dir(session, "/home/me", log.append, "", 30)
    assert d == "/home/me/vpconnect-configure"


def test_verify_configure_scripts_dir_ok() -> None:
    session = MagicMock()
    session.exec_command.return_value = (0, "", "")
    logs: list[str] = []
    verify_configure_scripts_dir(session, "/c/dir", logs.append, 10)
    assert "04_setsystemaccess.sh" in session.exec_command.call_args[0][0]


def test_verify_configure_scripts_dir_raises() -> None:
    session = MagicMock()
    session.exec_command.return_value = (1, "", "missing")
    logs: list[str] = []
    with pytest.raises(RuntimeError, match="Установка прекращена"):
        verify_configure_scripts_dir(session, "/bad", logs.append, 10)
