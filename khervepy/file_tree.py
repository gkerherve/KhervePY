"""Project file browser: a filtered ``QFileSystemModel`` in a tree.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from PyQt6.QtCore import QDir, QMimeData, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFileSystemModel, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTreeView,
)

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
    """A project tree with full explorer operations (copy/move/rename/DnD)."""

    file_activated = pyqtSignal(str)
    changed = pyqtSignal()  # a file operation altered the tree

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path = ""
        self._clip_paths: list[str] = []  # internal cut/copy buffer
        self._clip_cut = False

        self._model = _GitFileSystemModel(self)
        self._model.setFilter(
            QDir.Filter.AllDirs
            | QDir.Filter.Files
            | QDir.Filter.NoDotAndDotDot
        )
        self._model.setNameFilterDisables(False)
        self._model.setReadOnly(False)  # allow rename + drag-move on disk
        self.setModel(self._model)

        # Show only the name column.
        for col in range(1, self._model.columnCount()):
            self.setColumnHidden(col, True)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(14)
        self.setSortingEnabled(False)

        # Selection + drag-and-drop (files are moved on disk by the model).
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        # Double-click opens files; rename is explicit (F2), never on click.
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.doubleClicked.connect(self._on_double_click)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self._install_shortcuts()

    # --- setup -----------------------------------------------------------
    def _install_shortcuts(self) -> None:
        def act(shortcut, slot):
            a = QAction(self)
            a.setShortcut(QKeySequence(shortcut))
            a.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            a.triggered.connect(slot)
            self.addAction(a)

        act("F2", self._rename)
        act("Delete", self._delete)
        act(QKeySequence.StandardKey.Copy, self._copy)
        act(QKeySequence.StandardKey.Cut, self._cut)
        act(QKeySequence.StandardKey.Paste, self._paste)

    def set_root(self, path: str) -> None:
        self._root_path = path
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

    # --- context menu ----------------------------------------------------
    def _context_menu(self, pos) -> None:
        index = self.indexAt(pos)
        menu = QMenu(self)
        menu.addAction("New File…", self._new_file)
        menu.addAction("New Folder…", self._new_folder)
        menu.addSeparator()
        if index.isValid():
            menu.addAction("Cut", self._cut)
            menu.addAction("Copy", self._copy)
        paste = menu.addAction("Paste", self._paste)
        paste.setEnabled(bool(self._clip_paths) or bool(self._os_clip_paths()))
        if index.isValid():
            menu.addAction("Duplicate", self._duplicate)
            menu.addSeparator()
            menu.addAction("Rename", self._rename)
            menu.addAction("Delete", self._delete)
            menu.addSeparator()
            menu.addAction("Copy Path", self._copy_path)
        menu.addAction("Reveal in File Explorer", self._reveal)
        menu.exec(self.viewport().mapToGlobal(pos))

    # --- helpers ---------------------------------------------------------
    def _selected_paths(self) -> list[str]:
        seen: list[str] = []
        for idx in self.selectedIndexes():
            if idx.column() == 0:
                p = self._model.filePath(idx)
                if p not in seen:
                    seen.append(p)
        return seen

    def _target_dir(self) -> str:
        idx = self.currentIndex()
        if idx.isValid():
            p = self._model.filePath(idx)
            return p if os.path.isdir(p) else os.path.dirname(p)
        return self._root_path or self._model.rootPath()

    def _select_path(self, path: str) -> None:
        idx = self._model.index(path)
        if idx.isValid():
            self.setCurrentIndex(idx)
            self.scrollTo(idx)

    @staticmethod
    def _dedupe(path: str) -> str:
        if not os.path.exists(path):
            return path
        parent = os.path.dirname(path)
        stem, ext = os.path.splitext(os.path.basename(path))
        i = 1
        while True:
            suffix = "copy" if i == 1 else f"copy {i}"
            cand = os.path.join(parent, f"{stem} {suffix}{ext}")
            if not os.path.exists(cand):
                return cand
            i += 1

    def _os_clip_paths(self) -> list[str]:
        md = QApplication.clipboard().mimeData()
        if md.hasUrls():
            return [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
        return []

    def _set_os_clip(self, paths: list[str]) -> None:
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(p) for p in paths])
        QApplication.clipboard().setMimeData(md)

    # --- operations ------------------------------------------------------
    def _new_file(self) -> None:
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if not ok or not name.strip():
            return
        path = os.path.join(self._target_dir(), name.strip())
        if os.path.exists(path):
            QMessageBox.warning(self, "New File", "That name already exists.")
            return
        try:
            with open(path, "a", encoding="utf-8"):
                pass
        except OSError as exc:
            QMessageBox.warning(self, "New File", str(exc))
            return
        self._select_path(path)
        self.changed.emit()
        self.file_activated.emit(path)

    def _new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        path = os.path.join(self._target_dir(), name.strip())
        try:
            os.makedirs(path, exist_ok=False)
        except OSError as exc:
            QMessageBox.warning(self, "New Folder", str(exc))
            return
        self._select_path(path)
        self.changed.emit()

    def _copy(self) -> None:
        paths = self._selected_paths()
        if paths:
            self._clip_paths, self._clip_cut = paths, False
            self._set_os_clip(paths)

    def _cut(self) -> None:
        paths = self._selected_paths()
        if paths:
            self._clip_paths, self._clip_cut = paths, True
            self._set_os_clip(paths)

    def _paste(self) -> None:
        dest = self._target_dir()
        paths = self._clip_paths or self._os_clip_paths()
        if not paths:
            return
        for src in paths:
            self._transfer(src, dest, move=self._clip_cut)
        if self._clip_cut:
            self._clip_paths = []
            self._clip_cut = False
        self.changed.emit()

    def _transfer(self, src: str, dest_dir: str, move: bool) -> None:
        if not os.path.exists(src):
            return
        target = os.path.join(dest_dir, os.path.basename(src))
        if os.path.abspath(src) == os.path.abspath(target):
            if move:
                return  # moving onto itself is a no-op
            target = self._dedupe(target)  # copy into same folder
        else:
            target = self._dedupe(target)
        try:
            if move:
                shutil.move(src, target)
            elif os.path.isdir(src):
                shutil.copytree(src, target)
            else:
                shutil.copy2(src, target)
        except (OSError, shutil.Error) as exc:
            QMessageBox.warning(self, "Paste failed", str(exc))

    def _duplicate(self) -> None:
        for src in self._selected_paths():
            self._transfer(src, os.path.dirname(src), move=False)
        self.changed.emit()

    def _rename(self) -> None:
        idx = self.currentIndex()
        if idx.isValid():
            self.edit(idx)  # inline editor; model renames on disk
            self.changed.emit()

    def _delete(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        listing = "\n".join(os.path.basename(p) for p in paths[:12])
        if len(paths) > 12:
            listing += f"\n… and {len(paths) - 12} more"
        answer = QMessageBox.question(
            self, "Delete",
            f"Permanently delete these {len(paths)} item(s)?\n\n{listing}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for p in paths:
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            except OSError as exc:
                QMessageBox.warning(self, "Delete failed", str(exc))
        self.changed.emit()

    def _copy_path(self) -> None:
        paths = self._selected_paths()
        if paths:
            QApplication.clipboard().setText("\n".join(paths))

    def _reveal(self) -> None:
        paths = self._selected_paths()
        target = paths[0] if paths else self._target_dir()
        try:
            if sys.platform.startswith("win"):
                subprocess.run(["explorer", "/select,", os.path.normpath(target)])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", target])
            else:
                subprocess.run(["xdg-open", os.path.dirname(target) or target])
        except OSError:
            pass
