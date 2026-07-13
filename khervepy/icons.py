"""Small, self-drawn line-glyph icons for the toolbar.

Icons are painted with ``QPainter`` at request time so there are no image
assets to ship and they take whatever colour the caller passes (so they adapt
to the OS light/dark toolbar palette). Each glyph is defined in a normalised
0..1 box and scaled to the requested pixel size.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)


def _P(px: int, x: float, y: float) -> QPointF:
    return QPointF(x * px, y * px)


def _poly(px: int, pts) -> QPolygonF:
    return QPolygonF([_P(px, x, y) for x, y in pts])


# --- glyphs -----------------------------------------------------------------
# Each takes (painter, px, color); the pen is already configured. Glyphs that
# need a fill set their own brush.
def _folder(p, px, color):
    p.drawPolyline(_poly(px, [
        (0.14, 0.30), (0.40, 0.30), (0.48, 0.40), (0.86, 0.40),
        (0.86, 0.76), (0.14, 0.76), (0.14, 0.30),
    ]))


def _file(p, px, color):
    p.drawPolyline(_poly(px, [
        (0.28, 0.16), (0.60, 0.16), (0.74, 0.30), (0.74, 0.84),
        (0.28, 0.84), (0.28, 0.16),
    ]))
    p.drawPolyline(_poly(px, [(0.60, 0.16), (0.60, 0.30), (0.74, 0.30)]))
    for y in (0.46, 0.58, 0.70):
        p.drawLine(_P(px, 0.36, y), _P(px, 0.66, y))


def _new(p, px, color):
    p.drawPolyline(_poly(px, [
        (0.26, 0.14), (0.58, 0.14), (0.72, 0.28), (0.72, 0.86),
        (0.26, 0.86), (0.26, 0.14),
    ]))
    p.drawPolyline(_poly(px, [(0.58, 0.14), (0.58, 0.28), (0.72, 0.28)]))
    p.drawLine(_P(px, 0.49, 0.46), _P(px, 0.49, 0.70))
    p.drawLine(_P(px, 0.37, 0.58), _P(px, 0.61, 0.58))


def _save(p, px, color):
    p.drawPolyline(_poly(px, [
        (0.20, 0.20), (0.66, 0.20), (0.80, 0.34), (0.80, 0.80),
        (0.20, 0.80), (0.20, 0.20),
    ]))
    p.drawPolyline(_poly(px, [
        (0.34, 0.20), (0.34, 0.34), (0.60, 0.34), (0.60, 0.20),
    ]))
    p.drawRect(QRectF(_P(px, 0.32, 0.50), _P(px, 0.68, 0.78)))


def _run(p, px, color):
    p.setBrush(QBrush(color))
    p.drawPolygon(_poly(px, [(0.30, 0.20), (0.30, 0.80), (0.80, 0.50)]))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _stop(p, px, color):
    p.setBrush(QBrush(color))
    p.drawRoundedRect(
        QRectF(_P(px, 0.30, 0.30), _P(px, 0.70, 0.70)), px * 0.06, px * 0.06
    )
    p.setBrush(Qt.BrushStyle.NoBrush)


def _debug(p, px, color):
    p.drawEllipse(QRectF(_P(px, 0.34, 0.36), _P(px, 0.66, 0.80)))
    p.drawLine(_P(px, 0.5, 0.40), _P(px, 0.5, 0.76))
    # antennae
    p.drawLine(_P(px, 0.44, 0.38), _P(px, 0.38, 0.26))
    p.drawLine(_P(px, 0.56, 0.38), _P(px, 0.62, 0.26))
    # legs
    for y0, y1 in ((0.48, 0.44), (0.58, 0.58), (0.68, 0.72)):
        p.drawLine(_P(px, 0.34, y0), _P(px, 0.20, y1))
        p.drawLine(_P(px, 0.66, y0), _P(px, 0.80, y1))


def _terminal(p, px, color):
    p.drawRect(QRectF(_P(px, 0.16, 0.24), _P(px, 0.84, 0.76)))
    p.drawPolyline(_poly(px, [(0.26, 0.40), (0.36, 0.50), (0.26, 0.60)]))
    p.drawLine(_P(px, 0.44, 0.62), _P(px, 0.58, 0.62))


def _magnifier(p, px, cx=0.44, cy=0.44, r=0.20):
    p.drawEllipse(QRectF(_P(px, cx - r, cy - r), _P(px, cx + r, cy + r)))
    p.drawLine(_P(px, cx + r * 0.7, cy + r * 0.7), _P(px, cx + r * 1.6, cy + r * 1.6))


def _find(p, px, color):
    _magnifier(p, px)


def _search(p, px, color):
    _magnifier(p, px, cx=0.44, cy=0.42, r=0.24)
    p.drawLine(_P(px, 0.34, 0.38), _P(px, 0.54, 0.38))
    p.drawLine(_P(px, 0.34, 0.48), _P(px, 0.54, 0.48))


def _replace(p, px, color):
    # two opposed arrows = swap/replace
    p.drawLine(_P(px, 0.22, 0.40), _P(px, 0.74, 0.40))
    p.drawPolyline(_poly(px, [(0.64, 0.32), (0.74, 0.40), (0.64, 0.48)]))
    p.drawLine(_P(px, 0.78, 0.60), _P(px, 0.26, 0.60))
    p.drawPolyline(_poly(px, [(0.36, 0.52), (0.26, 0.60), (0.36, 0.68)]))


def _find_in_files(p, px, color):
    p.drawPolyline(_poly(px, [
        (0.20, 0.16), (0.48, 0.16), (0.58, 0.26), (0.58, 0.62),
    ]))
    p.drawPolyline(_poly(px, [
        (0.20, 0.16), (0.20, 0.84), (0.46, 0.84),
    ]))
    for y in (0.32, 0.44):
        p.drawLine(_P(px, 0.28, y), _P(px, 0.50, y))
    _magnifier(p, px, cx=0.60, cy=0.62, r=0.15)


def _commit_push(p, px, color):
    p.drawLine(_P(px, 0.5, 0.34), _P(px, 0.5, 0.80))
    p.setBrush(QBrush(color))
    p.drawEllipse(QRectF(_P(px, 0.41, 0.55), _P(px, 0.59, 0.73)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolyline(_poly(px, [(0.36, 0.34), (0.5, 0.18), (0.64, 0.34)]))


def _clone(p, px, color):
    p.drawLine(_P(px, 0.5, 0.18), _P(px, 0.5, 0.56))
    p.drawPolyline(_poly(px, [(0.36, 0.42), (0.5, 0.58), (0.64, 0.42)]))
    p.drawPolyline(_poly(px, [
        (0.24, 0.62), (0.24, 0.80), (0.76, 0.80), (0.76, 0.62),
    ]))


def _fork(p, px, color):
    p.setBrush(QBrush(color))
    for cx, cy in ((0.32, 0.26), (0.68, 0.26), (0.5, 0.74)):
        p.drawEllipse(QRectF(_P(px, cx - 0.07, cy - 0.07), _P(px, cx + 0.07, cy + 0.07)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(_P(px, 0.5, 0.67), _P(px, 0.5, 0.50))
    p.drawPolyline(_poly(px, [(0.32, 0.33), (0.32, 0.44), (0.5, 0.50), (0.68, 0.44), (0.68, 0.33)]))


def _branch(p, px, color):
    # git-branch glyph: a trunk with one branch splitting off.
    p.drawLine(_P(px, 0.34, 0.24), _P(px, 0.34, 0.78))
    p.drawPolyline(_poly(px, [(0.34, 0.50), (0.52, 0.50), (0.64, 0.40)]))
    p.setBrush(QBrush(color))
    p.drawEllipse(QRectF(_P(px, 0.27, 0.70), _P(px, 0.41, 0.84)))  # trunk bottom
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(_P(px, 0.27, 0.18), _P(px, 0.41, 0.32)))  # trunk top
    p.setBrush(QBrush(color))
    p.drawEllipse(QRectF(_P(px, 0.59, 0.28), _P(px, 0.73, 0.42)))  # branch node
    p.setBrush(Qt.BrushStyle.NoBrush)


def _compact(p, px, color):
    # Diagonal double-arrow pointing inward = shrink to a compact cockpit.
    p.drawLine(_P(px, 0.24, 0.24), _P(px, 0.42, 0.42))
    p.drawPolyline(_poly(px, [(0.42, 0.28), (0.42, 0.42), (0.28, 0.42)]))
    p.drawLine(_P(px, 0.76, 0.76), _P(px, 0.58, 0.58))
    p.drawPolyline(_poly(px, [(0.58, 0.72), (0.58, 0.58), (0.72, 0.58)]))


def _maximise(p, px, color):
    # Diagonal double-arrow pointing outward = expand back to the full editor.
    p.drawLine(_P(px, 0.26, 0.26), _P(px, 0.44, 0.44))
    p.drawPolyline(_poly(px, [(0.26, 0.40), (0.26, 0.26), (0.40, 0.26)]))
    p.drawLine(_P(px, 0.74, 0.74), _P(px, 0.56, 0.56))
    p.drawPolyline(_poly(px, [(0.74, 0.60), (0.74, 0.74), (0.60, 0.74)]))


def _packages(p, px, color):
    p.drawRect(QRectF(_P(px, 0.24, 0.30), _P(px, 0.76, 0.80)))
    p.drawLine(_P(px, 0.5, 0.30), _P(px, 0.5, 0.80))
    p.drawLine(_P(px, 0.24, 0.44), _P(px, 0.76, 0.44))


_GLYPHS = {
    "branch": _branch,
    "folder": _folder,
    "file": _file,
    "new": _new,
    "save": _save,
    "run": _run,
    "stop": _stop,
    "debug": _debug,
    "terminal": _terminal,
    "find": _find,
    "replace": _replace,
    "find_in_files": _find_in_files,
    "search": _search,
    "commit_push": _commit_push,
    "clone": _clone,
    "fork": _fork,
    "packages": _packages,
    "compact": _compact,
    "maximise": _maximise,
}


def _render(draw, color: QColor, px: int) -> QPixmap:
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color)
    pen.setWidthF(max(1.3, px * 0.075))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    draw(p, px, color)
    p.end()
    return pm


def icon(name: str, color: QColor, sizes=(16, 24, 32, 48)) -> QIcon:
    """Return a multi-resolution ``QIcon`` for ``name`` drawn in ``color``."""
    draw = _GLYPHS.get(name)
    result = QIcon()
    if draw is None:
        return result
    for px in sizes:
        result.addPixmap(_render(draw, color, px))
    return result
