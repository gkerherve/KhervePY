"""The commit-history ("Log") dock — a VS Code–style commit graph.

Renders all branches with coloured lane rails, ref badges, author and date.
Double-clicking a commit shows its patch in the Diff dock.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from khervepy import git_backend as gb
from khervepy.commit_graph import GraphDelegate, build_lanes, max_lanes


class CommitLog(QWidget):
    """Commit graph bound to a working directory."""

    show_commit = pyqtSignal(str)  # full revision hash

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

        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setHeaderLabels(["Graph", "Description", "Author", "Date"])
        self.tree.setColumnWidth(0, 90)
        self.tree.itemDoubleClicked.connect(self._activate)
        self._delegate = GraphDelegate(lambda: self._rows, self.tree)
        self.tree.setItemDelegate(self._delegate)
        header = self.tree.header()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 1)

    # --- data ------------------------------------------------------------
    def set_repo(self, path: str) -> None:
        self.repo_path = path if path and gb.is_repo(path) else None
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
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

    def _activate(self, item: QTreeWidgetItem, _col: int) -> None:
        rev = item.data(0, Qt.ItemDataRole.UserRole)
        if rev:
            self.show_commit.emit(rev)
