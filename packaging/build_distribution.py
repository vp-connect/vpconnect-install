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


def _gui_artifact_basename() -> str:
    """Имя собранного бинарника PyInstaller на текущей ОС (на Windows — с .exe)."""
    return "vpconnect-install-gui.exe" if sys.platform == "win32" else "vpconnect-install-gui"


def _readme_common_body() -> str:
    """Общий текст про провижининг и сеть (без привязки к ОС сборки)."""
    return """\
This tool provisions a server over SSH (WireGuard, MTProxy, VPManage) using vpconnect-
configure scripts. The target server OS is one of three families: debian (Debian/Ubuntu),
centos (RHEL, Alma, Rocky, Fedora, Amazon Linux 2023+, …), or freebsd. See the main
README or vpconnect-configure README for exact supported releases.

Scripts 00–03 are fetched from GitHub raw; 03 clones the configure repo. Network access
to GitHub is required.
"""


def _write_dist_readme(version: str, *, skip_pyinstaller: bool) -> None:
    """Текст readme.txt зависит от ОС, на которой запущен build_distribution.py."""
    DIST.mkdir(parents=True, exist_ok=True)
    gui_name = _gui_artifact_basename()
    zip_line = (
        f"- {ZIP_NAME} — source tree + scripts; bootstrap per OS, then run (see README.md)."
    )
    pyi_note = (
        f"- {gui_name} — GUI built with PyInstaller on this machine (no separate Python to run it)."
        if not skip_pyinstaller
        else "- (PyInstaller was skipped for this run; there is no frozen GUI binary in dist/.)"
    )

    if sys.platform == "win32":
        body = f"""vpconnect-install distribution (built on Windows)

Version: {version}

Contents of this folder:
{pyi_note}
{zip_line}
- readme.txt — this file.

When you run the GUI executable, logs appear in the window. Artifacts are written to
provision-artifacts/ under the current working directory (the folder you start the program from).

{_readme_common_body()}
From the portable zip on Windows: unpack, then run scripts\\windows\\cmd\\bootstrap.bat or
scripts\\windows\\ps\\bootstrap.ps1, then:
  python -m vpconnect_install gui
  python -m vpconnect_install --help
"""

    elif sys.platform == "darwin":
        body = f"""vpconnect-install distribution (built on macOS)

Version: {version}

Contents of this folder:
{pyi_note}
{zip_line}
- readme.txt — this file.

{_readme_common_body()}
On this Mac, set up a venv from the repo or zip: ./bootstrap.sh or scripts/macos/bootstrap.sh,
then: python -m vpconnect_install gui (or CLI). Artifacts: provision-artifacts/ under the cwd.

A Windows-only .exe for operators without Python is produced when you run
packaging/build_distribution.py on a 64-bit Windows machine (see README.md).

From the portable zip on other systems, use scripts/linux/ or scripts/windows/… as in README.md.
"""

    else:
        # Linux and other POSIX (e.g. WSL reports linux)
        body = f"""vpconnect-install distribution (built on Linux)

Version: {version}

Contents of this folder:
{pyi_note}
{zip_line}
- readme.txt — this file.

{_readme_common_body()}
On this machine: ./bootstrap.sh or scripts/linux/bootstrap.sh, then:
  python -m vpconnect_install gui
Artifacts go to provision-artifacts/ under the current working directory.

A Windows .exe for users without Python is produced when packaging/build_distribution.py
is run on Windows (see README.md).

From the portable zip on macOS or Windows, follow README.md (scripts/macos or scripts/windows).
"""

    (DIST / "readme.txt").write_text(body, encoding="utf-8")


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


def _portable_zip_paths() -> list[Path]:
    include_dirs = [
        REPO_ROOT / "src",
        REPO_ROOT / "packaging",
        REPO_ROOT / "scripts",
    ]
    files = [
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "README.md",
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "requirements.txt",
        REPO_ROOT / "requirements-dev.txt",
        REPO_ROOT / "bootstrap.sh",
        REPO_ROOT / "bootstrap-dist.sh",
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
    _write_dist_readme(ver, skip_pyinstaller=args.skip_pyinstaller)
    _write_portable_zip()
    print(f"Done. Outputs under {DIST}:", flush=True)
    if not args.skip_pyinstaller:
        print(f"  - {_gui_artifact_basename()}", flush=True)
    print("  - readme.txt (text depends on build host OS)", flush=True)
    print(f"  - {ZIP_NAME}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
