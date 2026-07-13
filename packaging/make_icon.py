"""Generate the KhervePY application icon (PNG + ICO).

Draws the KherveTools house style: a rounded editor tile with a faint code grid
and a two-tone "Py" wordmark. Run headless:

    python packaging/make_icon.py

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication

HERE = os.path.dirname(os.path.abspath(__file__))


def render(size: int = 256) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    margin = size * 0.06
    radius = size * 0.22
    tile = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

    # Editor-tile gradient.
    grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
    grad.setColorAt(0.0, QColor("#2B2B2B"))
    grad.setColorAt(1.0, QColor("#3C3F41"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(tile, radius, radius)

    # Faint code grid.
    p.setClipRect(tile)
    p.setPen(QPen(QColor(255, 255, 255, 16), max(1.0, size / 256)))
    step = size / 10.0
    y = tile.top() + step
    while y < tile.bottom():
        p.drawLine(int(tile.left()), int(y), int(tile.right()), int(y))
        y += step
    p.setClipping(False)

    # Two-tone "Py" wordmark (Python blue + yellow).
    font = QFont("DejaVu Sans, Arial, sans-serif")
    font.setPixelSize(int(size * 0.5))
    font.setBold(True)
    p.setFont(font)
    metrics = p.fontMetrics()
    text_p, text_y = "P", "y"
    w_p = metrics.horizontalAdvance(text_p)
    w_y = metrics.horizontalAdvance(text_y)
    total = w_p + w_y
    x = (size - total) / 2
    baseline = size / 2 + metrics.ascent() / 2 - metrics.descent() / 2

    p.setPen(QColor("#4B8BBE"))
    p.drawText(int(x), int(baseline), text_p)
    p.setPen(QColor("#FFD43B"))
    p.drawText(int(x + w_p), int(baseline), text_y)

    p.end()
    return pix


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841 (QPainter needs a QApplication)
    png = os.path.join(HERE, "khervepy.png")
    ico = os.path.join(HERE, "khervepy.ico")
    big = render(256)
    if not big.save(png, "PNG"):
        print("failed to write PNG")
        return 1
    if not big.save(ico, "ICO"):
        print("failed to write ICO")
        return 1
    print(f"wrote {png} and {ico}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
