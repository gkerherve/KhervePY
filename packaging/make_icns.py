"""Render the KhervePY application icon as a macOS ``.icns``.

Uses the same painter as ``make_icon.py`` (so the Windows ``.ico``, the PNG
and the Mac icon are one drawing, crisp at every size) and Apple's own
``iconutil``::

    python packaging/make_icns.py [output.icns]     # default: build/KhervePY.icns

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_icon  # noqa: E402  (sets QT_QPA_PLATFORM=offscreen off Windows)
from PyQt6.QtWidgets import QApplication  # noqa: E402

# (file name, pixel size) of an .iconset: @1x and @2x of 16..512.
ICONSET = [
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
]


def make_icns(out: str) -> str:
    if sys.platform != "darwin":
        raise SystemExit("make_icns.py needs macOS (iconutil)")
    _app = QApplication.instance() or QApplication([])  # noqa: F841
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "KhervePY.iconset")
        os.makedirs(iconset)
        for name, size in ICONSET:
            if not make_icon.render(size).save(os.path.join(iconset, name)):
                raise SystemExit(f"could not write {name}")
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out], check=True)
    return out


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(HERE), "build", "KhervePY.icns")
    print(f"wrote {make_icns(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
