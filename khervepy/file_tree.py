"""Project file browser: a filtered ``QFileSystemModel`` in a tree.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtCore import QDir, pyqtSignal
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtWidgets import QTreeView


class FileTree(QTreeView):
    """A single-column project tree that emits :attr:`file_activated`."""

    file_activated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QFileSystemModel(self)
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

    def _on_double_click(self, index) -> None:
        path = self._model.filePath(index)
        if not self._model.isDir(index):
            self.file_activated.emit(path)

    def current_path(self) -> str:
        index = self.currentIndex()
        return self._model.filePath(index) if index.isValid() else ""
