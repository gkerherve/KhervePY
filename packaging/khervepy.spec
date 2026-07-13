# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for KhervePY.

Build a one-folder, windowed distribution from the repository root:

    pyinstaller packaging/khervepy.spec

Produces ``dist/KhervePY/`` containing the executable and its dependencies.

Copyright (C) 2026 Gwilherm Kerherve — GNU GPL v3 or later.
"""

import os

# SPECPATH is injected by PyInstaller and points at this file's directory.
PKG_DIR = SPECPATH
ROOT = os.path.dirname(PKG_DIR)
ENTRY = os.path.join(ROOT, "KhervePY.py")
ICON = os.path.join(PKG_DIR, "khervepy.ico")

datas = [
    (os.path.join(PKG_DIR, "khervepy.png"), "."),
    (os.path.join(PKG_DIR, "khervepy.ico"), "."),
]

a = Analysis(
    [ENTRY],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=["PyQt6.Qsci"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PySide6", "PyQt5"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KhervePY",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=ICON if os.path.isfile(ICON) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KhervePY",
)
