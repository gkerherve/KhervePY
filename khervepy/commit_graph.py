"""Commit-graph layout and painting — the coloured branch rails, VS Code style.

``build_lanes`` turns a topologically ordered commit list into per-row drawing
instructions (which lanes pass through, where the node sits, which edges fan out
to parents). ``GraphDelegate`` paints those rails and the node in column 0 and
ref badges + subject in column 1 of a ``QTreeWidget``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate

# Lane colours, cycled by column.
LANE_COLORS = [
    "#3592C4", "#E0533D", "#3FB950", "#D29922",
    "#A371F7", "#DB61A2", "#2AC3DE", "#F0883E",
]


def build_lanes(commits: list[dict]) -> list[dict]:
    """Return per-row layout dicts: ``commit``, ``node_col``, ``segments``.

    Each segment is ``(x0, y0, x1, y1, color_col)`` in lane / row-fraction
    coordinates (y 0=top, 0.5=node, 1=bottom).
    """
    lanes: list[str | None] = []  # each holds the full hash a lane descends to
    layout: list[dict] = []

    def first_empty() -> int:
        for i, x in enumerate(lanes):
            if x is None:
                return i
        lanes.append(None)
        return len(lanes) - 1

    for c in commits:
        h = c["full"]
        parents = c["parents"]

        mine = [i for i, x in enumerate(lanes) if x == h]
        col = mine[0] if mine else first_empty()
        lanes[col] = h
        incoming = list(lanes)

        # Collapse any other child lanes that were waiting for this commit.
        for i in mine:
            if i != col:
                lanes[i] = None

        extra_cols: list[int] = []
        if parents:
            lanes[col] = parents[0]
            for p in parents[1:]:
                existing = [i for i, x in enumerate(lanes) if x == p]
                pc = existing[0] if existing else first_empty()
                lanes[pc] = p
                extra_cols.append(pc)
        else:
            lanes[col] = None  # root commit

        outgoing = list(lanes)

        segments = []
        # Top half: every incoming lane routes down to its node or straight on.
        for i, x in enumerate(incoming):
            if x is None:
                continue
            target = col if x == h else i
            segments.append((i, 0.0, target, 0.5, i))
        # Bottom half: node fans out to parents; other lanes pass straight.
        for j, x in enumerate(outgoing):
            if x is None:
                continue
            if j == col or j in extra_cols:
                segments.append((col, 0.5, j, 1.0, j))
            else:
                segments.append((j, 0.5, j, 1.0, j))

        layout.append({"commit": c, "node_col": col, "segments": segments})

        while lanes and lanes[-1] is None:
            lanes.pop()

    return layout


def max_lanes(layout: list[dict]) -> int:
    width = 1
    for row in layout:
        width = max(width, row["node_col"] + 1)
        for (x0, _y0, x1, _y1, _c) in row["segments"]:
            width = max(width, int(x0) + 1, int(x1) + 1)
    return width


def _parse_refs(refs: str):
    """Yield ``(display, color)`` badges for a git ``%D`` decoration string."""
    for token in (t.strip() for t in refs.split(",") if t.strip()):
        if token.startswith("HEAD ->"):
            yield token[7:].strip(), "#2EA043"        # current branch
        elif token == "HEAD":
            yield "HEAD", "#2EA043"
        elif token.startswith("tag:"):
            yield token[4:].strip(), "#C9A227"        # tag
        elif "/" in token:
            yield token, "#8250DF"                     # remote branch
        else:
            yield token, "#1F6FEB"                     # local branch


class GraphDelegate(QStyledItemDelegate):
    """Paints the graph column and the ref-badge/subject column."""

    LANE_W = 16
    DOT_R = 4.0

    def __init__(self, rows_getter, parent=None):
        super().__init__(parent)
        self._rows = rows_getter  # callable -> current layout list

    # --- painting --------------------------------------------------------
    def paint(self, painter, option, index):
        col = index.column()
        rows = self._rows()
        r = index.row()
        if col == 0 and 0 <= r < len(rows):
            painter.save()
            self._selection_bg(painter, option)
            self._paint_graph(painter, option, rows[r])
            painter.restore()
            return
        if col == 1 and 0 <= r < len(rows):
            painter.save()
            self._selection_bg(painter, option)
            self._paint_desc(painter, option, rows[r]["commit"])
            painter.restore()
            return
        super().paint(painter, option, index)

    def _selection_bg(self, painter, option):
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

    def _paint_graph(self, painter, option, row):
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        rect = option.rect
        lw = self.LANE_W

        def px(x):
            return rect.x() + (x + 0.5) * lw

        def py(y):
            return rect.y() + y * rect.height()

        for (x0, y0, x1, y1, cidx) in row["segments"]:
            color = QColor(LANE_COLORS[int(cidx) % len(LANE_COLORS)])
            pen = QPen(color, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(int(px(x0)), int(py(y0)), int(px(x1)), int(py(y1)))

        node_col = row["node_col"]
        color = QColor(LANE_COLORS[node_col % len(LANE_COLORS)])
        painter.setBrush(color)
        painter.setPen(QPen(color.darker(140), 1.0))
        cx, cy = px(node_col), rect.center().y()
        painter.drawEllipse(QRectF(cx - self.DOT_R, cy - self.DOT_R,
                                   2 * self.DOT_R, 2 * self.DOT_R))

    def _paint_desc(self, painter, option, commit):
        rect = option.rect
        fm = painter.fontMetrics()
        x = rect.x() + 4
        cy = rect.center().y()
        h = fm.height()

        for name, color in _parse_refs(commit.get("refs", "")):
            tw = fm.horizontalAdvance(name)
            bw = tw + 10
            badge = QRectF(x, cy - h / 2.0, bw, h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, name)
            x += bw + 4

        selected = option.state & QStyle.StateFlag.State_Selected
        painter.setPen(
            option.palette.highlightedText().color() if selected
            else option.palette.text().color()
        )
        avail = rect.right() - x - 6
        subj = fm.elidedText(commit.get("subject", ""),
                             Qt.TextElideMode.ElideRight, max(10, avail))
        painter.drawText(x, rect.y(), avail, rect.height(),
                         int(Qt.AlignmentFlag.AlignVCenter), subj)
