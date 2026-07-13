"""A commit-history ("Log") view for the current repository.

Lists recent commits with their branch/tag decorations, author and date;
double-clicking a commit shows its patch in the Diff dock.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
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


class CommitLog(QWidget):
    """Repository commit history, bound to a working directory."""

    show_commit = pyqtSignal(str)  # revision hash

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        top = QHBoxLayout()
        self.summary = QLabel("No repository.")
        top.addWidget(self.summary, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        top.addWidget(refresh)
        layout.addLayout(top)

        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(["Commit", "Author", "Date", "Hash"])
        self.tree.itemDoubleClicked.connect(self._activate)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 1)

    # --- data ------------------------------------------------------------
    def set_repo(self, path: str) -> None:
        self.repo_path = path if path and gb.is_repo(path) else None
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        if not self.repo_path:
            self.summary.setText("Not a Git repository.")
            return
        try:
            entries = gb.log_entries(self.repo_path)
        except gb.GitError as exc:
            self.summary.setText(f"git error: {exc}")
            return

        ref_font = QFont()
        ref_font.setBold(True)
        for e in entries:
            subject = e["subject"]
            refs = e.get("refs", "").strip()
            label = f"⟢ {refs}  {subject}" if refs else subject
            item = QTreeWidgetItem([label, e["author"], e["date"], e["hash"]])
            item.setData(0, Qt.ItemDataRole.UserRole, e["hash"])
            if refs:
                item.setForeground(0, QColor("#3592C4"))
                item.setFont(0, ref_font)
            self.tree.addTopLevelItem(item)
        self.summary.setText(f"{len(entries)} commit(s)")

    def _activate(self, item: QTreeWidgetItem, _col: int) -> None:
        rev = item.data(0, Qt.ItemDataRole.UserRole)
        if rev:
            self.show_commit.emit(rev)
