"""The commit-history ("Log") dock — a VS Code–style commit graph plus a
files-changed tree for the selected commit.

The graph (coloured branch rails, ref badges) sits above a folder tree of the
files touched by the selected commit; double-click a file to see that file's
patch, or double-click a commit row to see the whole patch.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from khervepy import git_backend as gb
from khervepy.commit_graph import GraphDelegate, build_lanes, max_lanes, _parse_refs

# Colour per change status.
_STATUS_COLOR = {
    "A": "#3FB950", "M": "#D29922", "D": "#F85149",
    "R": "#A371F7", "C": "#A371F7", "T": "#D29922",
}


def _refs_text(raw: str) -> str:
    """Comma-joined ref names for tooltips / the message panel."""
    return ", ".join(name for name, _color in _parse_refs(raw))


def _short_author(name: str) -> str:
    """``Gwilherm Kerherve`` -> ``G Kerherve`` (first initial + surname)."""
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]} {parts[-1]}"
    return name


def _friendly_date(raw: str) -> str:
    """Turn ``2026-07-13 16:26`` into ``Today 16:26`` / ``Yesterday 16:26`` /
    a weekday within the last week, else the plain date."""
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        return raw
    delta = (date.today() - dt.date()).days
    if delta == 0:
        return dt.strftime("Today %H:%M")
    if delta == 1:
        return dt.strftime("Yesterday %H:%M")
    if 1 < delta < 7:
        return dt.strftime("%a %H:%M")  # e.g. Mon 14:07
    return dt.strftime("%Y-%m-%d")


class CommitLog(QWidget):
    """Commit graph + per-commit files tree, bound to a working directory."""

    show_commit = pyqtSignal(str)             # full revision hash
    show_commit_file = pyqtSignal(str, str)   # (rev, file)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo_path: str | None = None
        self._rows: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        top = QHBoxLayout()
        self.summary = QLabel("No repository.")
        top.addWidget(self.summary, 1)
        self.all_cb = QCheckBox("All branches")
        self.all_cb.setChecked(True)
        self.all_cb.toggled.connect(self.refresh)
        top.addWidget(self.all_cb)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        top.addWidget(refresh)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Graph (top).
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setHeaderLabels(["Graph", "Description", "Date", "Author"])
        self.tree.setColumnWidth(0, 90)
        self.tree.itemDoubleClicked.connect(self._activate_commit)
        self.tree.currentItemChanged.connect(self._on_commit_selected)
        self._delegate = GraphDelegate(lambda: self._rows, self.tree)
        self.tree.setItemDelegate(self._delegate)
        header = self.tree.header()
        # Interactive on every column so the user can drag the dividers.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        self.tree.setColumnWidth(1, 300)  # Description
        self.tree.setColumnWidth(2, 110)  # Date
        self.tree.setColumnWidth(3, 120)  # Author
        splitter.addWidget(self.tree)

        # Full commit message (middle) — the graph's Description column is
        # truncated, so show the whole subject + body here for the selection.
        msg_panel = QWidget()
        mp = QVBoxLayout(msg_panel)
        mp.setContentsMargins(0, 4, 0, 0)
        mp.addWidget(QLabel("Commit message"))
        self.message = QPlainTextEdit()
        self.message.setReadOnly(True)
        self.message.setPlaceholderText("Select a commit to see its full message.")
        mp.addWidget(self.message, 1)
        splitter.addWidget(msg_panel)

        # Files changed (bottom).
        files_panel = QWidget()
        fp = QVBoxLayout(files_panel)
        fp.setContentsMargins(0, 4, 0, 0)
        self.files_label = QLabel("Files changed")
        fp.addWidget(self.files_label)
        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderHidden(True)
        self.files_tree.itemDoubleClicked.connect(self._activate_file)
        fp.addWidget(self.files_tree, 1)
        splitter.addWidget(files_panel)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        layout.addWidget(splitter, 1)

    # --- data ------------------------------------------------------------
    def set_repo(self, path: str) -> None:
        self.repo_path = path if path and gb.is_repo(path) else None
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        self.files_tree.clear()
        self.message.clear()
        self._rows = []
        if not self.repo_path:
            self.summary.setText("Not a Git repository.")
            return
        try:
            commits = gb.log_graph(self.repo_path, all_branches=self.all_cb.isChecked())
        except gb.GitError as exc:
            self.summary.setText(f"git error: {exc}")
            return

        self._rows = build_lanes(commits)
        # Graph column holds rails + small ref dots, so it stays narrow.
        lanes_px = max_lanes(self._rows) * GraphDelegate.LANE_W
        dots_px = max(
            (self._delegate.refs_span(row["commit"]) for row in self._rows),
            default=0,
        )
        self.tree.setColumnWidth(0, lanes_px + dots_px + 14)

        for row in self._rows:
            c = row["commit"]
            item = QTreeWidgetItem(
                ["", "", _friendly_date(c["date"]), _short_author(c["author"])]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, c["full"])
            refs = _refs_text(c.get("refs", ""))
            if refs:
                item.setData(0, Qt.ItemDataRole.UserRole + 1, refs)
                item.setToolTip(0, refs)
                item.setToolTip(1, refs)
            self.tree.addTopLevelItem(item)
        self.summary.setText(f"{len(self._rows)} commit(s)")
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    # --- files tree ------------------------------------------------------
    def _on_commit_selected(self, current, _previous) -> None:
        self.files_tree.clear()
        self.message.clear()
        if current is None or not self.repo_path:
            return
        rev = current.data(0, Qt.ItemDataRole.UserRole)
        if not rev:
            return
        try:
            msg = gb.commit_message(self.repo_path, rev).strip()
        except gb.GitError:
            msg = ""
        refs = current.data(0, Qt.ItemDataRole.UserRole + 1)
        if refs:  # describe the graph's ref dots here
            msg = f"Refs: {refs}\n\n{msg}" if msg else f"Refs: {refs}"
        self.message.setPlainText(msg)
        try:
            files = gb.commit_files(self.repo_path, rev)
        except gb.GitError:
            return
        self.files_label.setText(f"Files changed ({len(files)})")
        folders: dict[str, QTreeWidgetItem] = {}
        for status, fpath in files:
            parent = self.files_tree.invisibleRootItem()
            cur = ""
            parts = fpath.split("/")
            for i, part in enumerate(parts):
                cur = f"{cur}/{part}" if cur else part
                existing = folders.get(cur)
                if existing is not None:
                    parent = existing
                    continue
                node = QTreeWidgetItem([part])
                parent.addChild(node)
                folders[cur] = node
                if i == len(parts) - 1:  # leaf = file
                    node.setData(0, Qt.ItemDataRole.UserRole, (rev, fpath))
                    node.setForeground(0, QColor(_STATUS_COLOR.get(status, "#8B949E")))
                    node.setToolTip(0, f"{status}  {fpath}")
                parent = node
        self.files_tree.expandAll()

    def _activate_file(self, item: QTreeWidgetItem, _col: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            rev, fpath = data
            self.show_commit_file.emit(rev, fpath)

    def _activate_commit(self, item: QTreeWidgetItem, _col: int) -> None:
        rev = item.data(0, Qt.ItemDataRole.UserRole)
        if rev:
            self.show_commit.emit(rev)
