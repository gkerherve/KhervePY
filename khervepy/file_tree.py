"""Project file browser: a filtered ``QFileSystemModel`` in a tree.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QDir, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFileSystemModel
from PyQt6.QtWidgets import QTreeView

# Git-status → filename colour. Added/untracked green, modified blue,
# deleted red, conflicted amber.
_STATUS_COLOR = {
    "?": QColor("#3FB950"), "A": QColor("#3FB950"),
    "M": QColor("#58A6FF"), "T": QColor("#58A6FF"),
    "R": QColor("#58A6FF"), "C": QColor("#58A6FF"),
    "D": QColor("#F85149"), "U": QColor("#D29922"),
}
_DIR_COLOR = QColor("#58A6FF")  # a folder that contains uncommitted changes


class _GitFileSystemModel(QFileSystemModel):
    """A filesystem model that tints changed files by their git status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status: dict[str, str] = {}

    def set_status_map(self, mapping: dict[str, str]) -> None:
        self._status = mapping or {}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.ForegroundRole and self._status:
            color = self._color_for(index)
            if color is not None:
                return color
        return super().data(index, role)

    def _color_for(self, index):
        path = os.path.normcase(os.path.abspath(self.filePath(index)))
        code = self._status.get(path)
        if code is not None:
            return _STATUS_COLOR.get(code)
        # A directory is tinted if it contains any changed file.
        if self.isDir(index):
            prefix = path + os.sep
            if any(p.startswith(prefix) for p in self._status):
                return _DIR_COLOR
        return None


class FileTree(QTreeView):
    """A single-column project tree that emits :attr:`file_activated`."""

    file_activated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = _GitFileSystemModel(self)
        self._model.setFilter(
            QDir.Filter.AllDirs
            | QDir.Filter.Files
            | QDir.Filter.NoDotAndDotDot
        )
        self._model.setNameFilterDisables(False)
        self.setModel(self._model)

        # Show only the name column.
        for col in range(1, self._model.columnCount()):
            self.setColumnHidden(col, True)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(14)
        self.setSortingEnabled(False)

        self.doubleClicked.connect(self._on_double_click)

    def set_root(self, path: str) -> None:
        index = self._model.setRootPath(path)
        self.setRootIndex(index)

    def set_status_map(self, mapping: dict[str, str]) -> None:
        """Recolour filenames from a ``path -> git-status`` mapping."""
        self._model.set_status_map(mapping)
        self.viewport().update()

    def _on_double_click(self, index) -> None:
        path = self._model.filePath(index)
        if not self._model.isDir(index):
            self.file_activated.emit(path)

    def current_path(self) -> str:
        index = self.currentIndex()
        return self._model.filePath(index) if index.isValid() else ""
