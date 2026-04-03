"""Resolve paths to bundled remote scripts (editable install, wheel, PyInstaller)."""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path


def remote_script_bytes(name: str) -> bytes:
    """Load bundled remote shell script by filename (e.g. finalize.sh)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "vpconnect_install" / "remote" / name
        return base.read_bytes()
    pkg_files = resources.files("vpconnect_install.remote")
    return (pkg_files / name).read_bytes()
