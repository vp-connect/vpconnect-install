"""Точка входа python -m vpconnect_install."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


def test_main_cli_path_exits_with_code() -> None:
    import vpconnect_install.__main__ as entry

    with patch.object(sys, "argv", ["vpconnect_install"]):
        with patch("vpconnect_install.cli.main", return_value=0):
            with pytest.raises(SystemExit) as exc_info:
                entry.main()
            assert exc_info.value.code == 0


def test_main_gui_branch_imports_gui() -> None:
    import vpconnect_install.__main__ as entry

    with patch.object(sys, "argv", ["vpconnect_install", "gui"]):
        with patch("vpconnect_install.gui_tk.main") as gui_main:
            entry.main()
            gui_main.assert_called_once()
