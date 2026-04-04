#!/usr/bin/env python3
"""Build Windows exe, dist/readme.txt, and portable source zip. Run from repo root."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = REPO_ROOT / "packaging" / "vpconnect-install-gui.spec"
DIST = REPO_ROOT / "dist"
ZIP_NAME = "vpconnect-install-portable.zip"


def _run_pyinstaller() -> None:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(DIST),
        "--workpath",
        str(REPO_ROOT / "build"),
        str(SPEC),
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def _write_exe_readme(version: str) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    text = f"""vpconnect-install GUI (Windows x64)

Version: {version}

Requires: Windows 10 or later (64-bit). No separate Python install.

This program provisions a server over SSH (WireGuard, MTProxy, VPManage) using vpconnect-
configure scripts. Target OS is one of three families: debian (Debian/Ubuntu, apt),
centos (RHEL, Alma, Rocky, Fedora, Amazon Linux 2023+, …), or freebsd. See the main
README or vpconnect-configure README for exact supported releases.

Logs appear in the window. Artifacts go to provision-artifacts/ under the current working
directory (the folder you start the .exe from).

Scripts 00–03 are fetched from GitHub raw; 03 clones the configure repo. Network access
to GitHub is required.

For CLI or running from source: use the portable zip and install_venv.bat / install_venv.sh.
"""
    (DIST / "readme.txt").write_text(text, encoding="utf-8")


def _portable_zip_paths() -> list[Path]:
    include_dirs = [REPO_ROOT / "src", REPO_ROOT / "packaging"]
    files = [
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "README.md",
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "requirements.txt",
        REPO_ROOT / "requirements-dev.txt",
        REPO_ROOT / "scripts" / "install_venv.sh",
        REPO_ROOT / "scripts" / "install_venv.bat",
    ]
    out: list[Path] = []
    for d in include_dirs:
        if d.is_dir():
            for p in d.rglob("*"):
                if p.is_file():
                    if _skip_path(p):
                        continue
                    out.append(p)
    for f in files:
        if f.is_file():
            out.append(f)
    return sorted(set(out))


def _skip_path(p: Path) -> bool:
    parts = set(p.parts)
    if "__pycache__" in parts:
        return True
    if ".git" in parts:
        return True
    return False


def _write_portable_zip() -> None:
    zpath = DIST / ZIP_NAME
    zpath.parent.mkdir(parents=True, exist_ok=True)
    root_name = REPO_ROOT.name
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_path in _portable_zip_paths():
            arc = root_name / abs_path.relative_to(REPO_ROOT)
            zf.write(abs_path, arc.as_posix())


def main() -> int:
    ap = argparse.ArgumentParser(description="Build vpconnect-install distribution artifacts.")
    ap.add_argument(
        "--skip-pyinstaller",
        action="store_true",
        help="Only rebuild readme.txt and portable zip",
    )
    args = ap.parse_args()
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from vpconnect_install.version import __version__ as ver

    if not args.skip_pyinstaller:
        _run_pyinstaller()
    _write_exe_readme(ver)
    _write_portable_zip()
    print(f"Done. Outputs under {DIST}:", flush=True)
    print("  - vpconnect-install-gui.exe", flush=True)
    print("  - readme.txt", flush=True)
    print(f"  - {ZIP_NAME}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
