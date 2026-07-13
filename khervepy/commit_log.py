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

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from khervepy import git_backend as gb
from khervepy.commit_graph import GraphDelegate, build_lanes, max_lanes

# Colour per change status.
_STATUS_COLOR = {
    "A": "#3FB950", "M": "#D29922", "D": "#F85149",
    "R": "#A371F7", "C": "#A371F7", "T": "#D29922",
}


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
        self.tree.setHeaderLabels(["Graph", "Description", "Author", "Date"])
        self.tree.setColumnWidth(0, 90)
        self.tree.itemDoubleClicked.connect(self._activate_commit)
        self.tree.currentItemChanged.connect(self._on_commit_selected)
        self._delegate = GraphDelegate(lambda: self._rows, self.tree)
        self.tree.setItemDelegate(self._delegate)
        header = self.tree.header()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        splitter.addWidget(self.tree)

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

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    # --- data ------------------------------------------------------------
    def set_repo(self, path: str) -> None:
        self.repo_path = path if path and gb.is_repo(path) else None
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        self.files_tree.clear()
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
        self.tree.setColumnWidth(0, max_lanes(self._rows) * GraphDelegate.LANE_W + 12)

        for row in self._rows:
            c = row["commit"]
            item = QTreeWidgetItem(["", "", c["author"], c["date"]])
            item.setData(0, Qt.ItemDataRole.UserRole, c["full"])
            self.tree.addTopLevelItem(item)
        self.summary.setText(f"{len(self._rows)} commit(s)")
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    # --- files tree ------------------------------------------------------
    def _on_commit_selected(self, current, _previous) -> None:
        self.files_tree.clear()
        if current is None or not self.repo_path:
            return
        rev = current.data(0, Qt.ItemDataRole.UserRole)
        if not rev:
            return
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
