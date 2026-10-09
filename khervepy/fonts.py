"""One place that picks the monospace font.

Qt takes a single family name, not a CSS-style list: ``QFont("Consolas, Menlo,
monospace")`` names a family that does not exist, and Qt silently falls back to
the *proportional* UI font — which on macOS (no Consolas) made the editor look
like prose. Ask the font database instead.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

# Best first: the platform's own coding fonts, then the widely installed ones.
_PREFERRED = ("SF Mono", "Menlo", "Consolas", "Cascadia Mono", "DejaVu Sans Mono",
              "Liberation Mono", "Monaco", "Courier New")


def mono_family() -> str:
    from PyQt6.QtGui import QFontDatabase

    available = set(QFontDatabase.families())
    for name in _PREFERRED:
        if name in available:
            return name
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def mono_font(size: int = 11):
    """A fixed-pitch QFont of *size* points."""
    from PyQt6.QtGui import QFont

    font = QFont(mono_family(), size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font
