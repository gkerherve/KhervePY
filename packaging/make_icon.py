"""Generate the KhervePY application icon (PNG + ICO).

Draws the KherveTools house style: a rounded editor tile with a faint code grid
and a three-tone "KPy" wordmark. Run headless:

    python packaging/make_icon.py

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import struct
import sys

# The offscreen platform ships no font database on Windows, so text would draw
# as tofu boxes. Painting to a QPixmap needs no window, so use the native
# platform there and keep offscreen for headless Linux/CI.
if os.name != "nt":
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

# Sizes Windows picks between for the taskbar, Explorer and Alt-Tab.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _sans_family() -> str:
    """Return the first installed sans-serif family from our preference list."""
    from PyQt6.QtGui import QFontDatabase

    available = set(QFontDatabase.families())
    for name in ("Segoe UI", "Arial", "DejaVu Sans", "Helvetica"):
        if name in available:
            return name
    return "sans-serif"


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

    # "KPy" wordmark: Kherve white K, then Python blue + yellow.
    # A comma-separated list is *not* a family name to Qt — it would resolve to
    # nothing and draw tofu boxes. Ask for one family and let the style hint
    # pick the platform's sans-serif if it is missing.
    font = QFont(_sans_family())
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPixelSize(int(size * 0.42))
    font.setBold(True)
    p.setFont(font)
    metrics = p.fontMetrics()
    parts = [("K", QColor("#E8E8E8")), ("P", QColor("#4B8BBE")), ("y", QColor("#FFD43B"))]
    total = sum(metrics.horizontalAdvance(t) for t, _ in parts)
    x = (size - total) / 2
    baseline = size / 2 + metrics.ascent() / 2 - metrics.descent() / 2

    for text, colour in parts:
        p.setPen(colour)
        p.drawText(int(x), int(baseline), text)
        x += metrics.horizontalAdvance(text)

    p.end()
    return pix


def _write_multi_ico(path: str, sizes) -> None:
    """Write a multi-resolution .ico containing a native render per size.

    Qt's ICO writer only ever stores a single image, so assemble the container
    by hand. Each entry holds a PNG payload, which Windows has read since
    Vista and which keeps the file small at 256px.
    """
    from PyQt6.QtCore import QBuffer, QByteArray

    payloads = []
    for size in sizes:
        # Bind the QByteArray to a name: QBuffer only borrows it, and letting
        # the temporary be collected crashes the interpreter.
        store = QByteArray()
        buf = QBuffer(store)
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        render(size).save(buf, "PNG")
        buf.close()
        payloads.append((size, bytes(store)))

    header = struct.pack("<HHH", 0, 1, len(payloads))  # reserved, type=icon, count
    offset = len(header) + 16 * len(payloads)
    entries, blobs = b"", b""
    for size, data in payloads:
        byte = 0 if size >= 256 else size  # 256 is encoded as 0
        entries += struct.pack("<BBBBHHII", byte, byte, 0, 0, 1, 32,
                               len(data), offset)
        blobs += data
        offset += len(data)
    with open(path, "wb") as fh:
        fh.write(header + entries + blobs)


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841 (QPainter needs a QApplication)
    png = os.path.join(HERE, "khervepy.png")
    ico = os.path.join(HERE, "khervepy.ico")
    big = render(256)
    if not big.save(png, "PNG"):
        print("failed to write PNG")
        return 1

    # Draw each ICO size natively rather than saving one 256px image and
    # letting Windows downscale it — the wordmark stays legible at 16/32px,
    # where the taskbar and Explorer actually show it.
    _write_multi_ico(ico, ICO_SIZES)
    print(f"wrote {png} and {ico} ({', '.join(str(s) for s in ICO_SIZES)}px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
