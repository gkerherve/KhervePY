"""Build KhervePY distributables: a frozen app, a zip archive, and (on
Windows, if Inno Setup is installed) an installer.

    python build.py                 # freeze + zip
    python build.py --installer     # also build the Inno Setup installer
    python build.py --clean         # remove build/ dist/ Output/ first

Runs from the repository root. Requires PyInstaller (see requirements-dev.txt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.join(ROOT, "packaging")
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
OUTPUT = os.path.join(ROOT, "Output")
APP_DIST = os.path.join(DIST, "KhervePY")


def _version() -> str:
    sys.path.insert(0, ROOT)
    from khervepy import __version__

    return __version__


def _platform_tag() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def clean() -> None:
    for path in (BUILD, DIST, OUTPUT):
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"removed {path}")


def ensure_icon() -> None:
    ico = os.path.join(PKG_DIR, "khervepy.ico")
    if not os.path.isfile(ico):
        print("icon missing — generating…")
        subprocess.run([sys.executable, os.path.join(PKG_DIR, "make_icon.py")],
                       check=True)


def freeze() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller is not installed. Run: pip install -r requirements-dev.txt")
    spec = os.path.join(PKG_DIR, "khervepy.spec")
    print("running PyInstaller…")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", spec],
        cwd=ROOT, check=True,
    )
    if not os.path.isdir(APP_DIST):
        sys.exit("PyInstaller did not produce dist/KhervePY")


def make_zip(version: str) -> str:
    base = os.path.join(DIST, f"KhervePY-{version}-{_platform_tag()}")
    archive = shutil.make_archive(base, "zip", root_dir=DIST, base_dir="KhervePY")
    print(f"wrote {archive}")
    return archive


def make_installer(version: str) -> None:
    if not sys.platform.startswith("win"):
        print("installer: skipped (Inno Setup runs on Windows only).")
        return
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    if not iscc:
        print("installer: skipped (Inno Setup 'iscc' not found on PATH).")
        return
    iss = os.path.join(PKG_DIR, "khervepy.iss")
    print("running Inno Setup…")
    subprocess.run(
        [iscc, f"/DMyAppVersion={version}", iss],
        cwd=PKG_DIR, check=True,
    )
    print(f"installer written to {OUTPUT}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KhervePY distributables.")
    parser.add_argument("--installer", action="store_true",
                        help="also build the Inno Setup installer (Windows)")
    parser.add_argument("--clean", action="store_true",
                        help="remove build/ dist/ Output/ before building")
    args = parser.parse_args()

    version = _version()
    print(f"KhervePY {version} — building for {_platform_tag()}")

    if args.clean:
        clean()
    ensure_icon()
    freeze()
    make_zip(version)
    if args.installer:
        make_installer(version)
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
