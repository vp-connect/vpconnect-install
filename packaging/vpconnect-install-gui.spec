# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Tk GUI (windowed). Run from repo root:
    pyinstaller packaging/vpconnect-install-gui.spec
"""
from pathlib import Path

# PyInstaller sets SPECPATH to the directory that contains the spec file.
_packaging = Path(SPECPATH).resolve()
repo_root = _packaging.parent
src_root = repo_root / "src"
remote_dir = src_root / "vpconnect_install" / "remote"

a = Analysis(
    [str(src_root / "vpconnect_install" / "gui_tk.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=[(str(remote_dir), "vpconnect_install/remote")],
    hiddenimports=["vpconnect_install", "vpconnect_install.remote"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="vpconnect-install-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
