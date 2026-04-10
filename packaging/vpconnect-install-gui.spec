# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Tk GUI (windowed). Run from repo root:
    pyinstaller packaging/vpconnect-install-gui.spec
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# PyInstaller sets SPECPATH to the directory that contains the spec file.
_packaging = Path(SPECPATH).resolve()
repo_root = _packaging.parent
src_root = repo_root / "src"

# Tkinter + Tcl/Tk data/libs are easy to miss in onefile builds; bundle the whole tree.
_tk_datas, _tk_binaries, _tk_hidden = collect_all("tkinter")

a = Analysis(
    [str(src_root / "vpconnect_install" / "gui_tk.py")],
    pathex=[str(src_root)],
    binaries=_tk_binaries,
    datas=_tk_datas,
    hiddenimports=[
        "vpconnect_install",
        "vpconnect_install.gui_clipboard",
        "_tkinter",
        "tkinter",
        "tkinter.constants",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.scrolledtext",
        "tkinter.ttk",
        *_tk_hidden,
    ],
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
    # UPX can break Tcl/Tk DLLs on Windows; keep off for GUI builds.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
