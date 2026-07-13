"""Locate bundled resources whether running from source or a frozen build.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import sys


def _candidates(filename: str):
    # 1. PyInstaller unpacks datas next to the executable (sys._MEIPASS).
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        yield os.path.join(meipass, filename)
    # 2. Running from source: <repo>/packaging/<filename>.
    here = os.path.dirname(os.path.abspath(__file__))
    yield os.path.join(here, os.pardir, "packaging", filename)
    # 3. Alongside the package (defensive).
    yield os.path.join(here, filename)


def resource_path(filename: str) -> str:
    """Return the first existing path for ``filename`` or an empty string."""
    for path in _candidates(filename):
        if os.path.isfile(path):
            return os.path.abspath(path)
    return ""


def icon_path() -> str:
    """Return the application icon path (PNG preferred, ICO fallback)."""
    return resource_path("khervepy.png") or resource_path("khervepy.ico")
