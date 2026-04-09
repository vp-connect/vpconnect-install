"""Покрытие блоков if __name__ == \"__main__\" через runpy."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
import pytest


def test_vpconnect_install_main_module_invokes_cli_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    main_py = Path(__file__).resolve().parents[1] / "src" / "vpconnect_install" / "__main__.py"
    monkeypatch.setattr(sys, "argv", [str(main_py), "--help"])
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(main_py), run_name="__main__")
    assert ei.value.code == 0


def test_cli_module_main_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cli_py = Path(__file__).resolve().parents[1] / "src" / "vpconnect_install" / "cli.py"
    monkeypatch.setattr(sys, "argv", [str(cli_py), "--help"])
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(cli_py), run_name="__main__")
    assert ei.value.code == 0


