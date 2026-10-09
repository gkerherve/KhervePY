# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for KhervePY.

Build a one-folder, windowed distribution from the repository root:

    pyinstaller packaging/khervepy.spec

Produces ``dist/KhervePY/`` containing the executable and its dependencies —
and, on macOS, ``dist/KhervePY.app`` (see ``packaging/build_macos.py``, which
generates the .icns first and signs the bundle afterwards).

Copyright (C) 2026 Gwilherm Kerherve — GNU GPL v3 or later.
"""

import os
import sys

# SPECPATH is injected by PyInstaller and points at this file's directory.
PKG_DIR = SPECPATH
ROOT = os.path.dirname(PKG_DIR)
ENTRY = os.path.join(ROOT, "KhervePY.py")
IS_MAC = sys.platform == "darwin"
ICON = os.path.join(PKG_DIR, "khervepy.ico")
# build_macos.py renders the .icns from the same code as the .ico/.png.
ICNS = os.path.join(ROOT, "build", "KhervePY.icns")

datas = [
    (os.path.join(PKG_DIR, "khervepy.png"), "."),
    (os.path.join(PKG_DIR, "khervepy.ico"), "."),
]

a = Analysis(
    [ENTRY],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PyQt6.Qsci",
        # Terminal emulator (macOS/Linux) and OS keychain backends.
        "pyte",
        "keyring.backends.macOS",
        "keyring.backends.Windows",
        "keyring.backends.SecretService",
        "keyring.backends.kwallet",
    ],
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
    upx=not IS_MAC,   # UPX corrupts Mach-O signatures
    console=False,
    disable_windowed_traceback=False,
    icon=ICON if (os.path.isfile(ICON) and not IS_MAC) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=not IS_MAC,
    upx_exclude=[],
    name="KhervePY",
)

if IS_MAC:
    sys.path.insert(0, ROOT)
    from khervepy import __version__

    # Build number: the commit count, so macOS can tell which build is newer.
    # (CFBundleShortVersionString is the marketing version, __version__.)
    build_number = os.environ.get("KHERVEPY_BUILD", __version__)

    _text = ["public.plain-text", "public.source-code", "public.script",
             "public.python-script", "public.json", "public.xml",
             "net.daringfireball.markdown"]
    app = BUNDLE(
        coll,
        name="KhervePY.app",
        icon=ICNS if os.path.isfile(ICNS) else None,
        bundle_identifier="com.kerherve.khervepy",
        info_plist={
            "CFBundleName": "KhervePY",
            "CFBundleDisplayName": "KhervePY",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": build_number,
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.developer-tools",
            "NSHumanReadableCopyright": "\u00a9 2026 Gwilherm Kerherve",
            # "Open With > KhervePY" for any text/code file; Alternate keeps
            # KhervePY from stealing the default app for them.
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Text and source files",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": _text,
            }],
        },
    )
