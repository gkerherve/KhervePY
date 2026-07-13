"""A persistent, project-wide text-search dock.

Unlike the modal Find-in-Files dialog, this lives in a dock so search results
stay available while you edit. Searching runs on a worker thread so large
projects don't freeze the UI.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import re

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from khervepy.find import compile_query, iter_text_files


class _SearchWorker(QObject):
    """Walks the project off-thread and reports matches per file."""

    file_matched = pyqtSignal(str, list)  # (path, [(lineno, text), ...])
    finished = pyqtSignal(int, int)       # (total_matches, files)

    def __init__(self, root: str, rx: re.Pattern):
        super().__init__()
        self._root = root
        self._rx = rx
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        total, files = 0, 0
        for path in iter_text_files(self._root):
            if self._stop:
                break
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            hits = [(i + 1, ln.rstrip()[:200])
                    for i, ln in enumerate(lines) if self._rx.search(ln)]
            if hits:
                files += 1
                total += len(hits)
                self.file_matched.emit(path, hits)
        self.finished.emit(total, files)


class SearchDock(QWidget):
    """Search box + live results tree, emitting :attr:`open_location`."""

    open_location = pyqtSignal(str, int)  # (path, line)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root = os.getcwd()
        self._thread: QThread | None = None
        self._worker: _SearchWorker | None = None
        self._build_ui()

    def set_root(self, root: str) -> None:
        self.root = root

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.query = QLineEdit()
        self.query.setPlaceholderText("Search project…  (Enter)")
        self.query.returnPressed.connect(self.search)
        layout.addWidget(self.query)

        opts = QHBoxLayout()
        self.case_cb = QCheckBox("Aa")
        self.case_cb.setToolTip("Case sensitive")
        self.word_cb = QCheckBox("W")
        self.word_cb.setToolTip("Whole word")
        self.regex_cb = QCheckBox(".*")
        self.regex_cb.setToolTip("Regex")
        opts.addWidget(self.case_cb)
        opts.addWidget(self.word_cb)
        opts.addWidget(self.regex_cb)
        opts.addStretch(1)
        self.summary = QLabel("")
        opts.addWidget(self.summary)
        layout.addLayout(opts)

        self.results = QTreeWidget()
        self.results.setHeaderHidden(True)
        self.results.itemDoubleClicked.connect(self._activate)
        layout.addWidget(self.results, 1)

    # --- search ----------------------------------------------------------
    def focus_query(self) -> None:
        self.query.setFocus()
        self.query.selectAll()

    def search(self) -> None:
        self._stop_running()
        self.results.clear()
        try:
            rx = compile_query(
                self.query.text(),
                self.case_cb.isChecked(),
                self.word_cb.isChecked(),
                self.regex_cb.isChecked(),
            )
        except re.error as exc:
            self.summary.setText(f"bad regex: {exc}")
            return
        if rx is None:
            return

        self.summary.setText("searching…")
        self._thread = QThread(self)
        self._worker = _SearchWorker(self.root, rx)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.file_matched.connect(self._add_file)
        self._worker.finished.connect(self._done)
        self._thread.start()

    def _add_file(self, path: str, hits: list) -> None:
        rel = os.path.relpath(path, self.root)
        parent = QTreeWidgetItem([f"{rel}  ({len(hits)})"])
        parent.setData(0, Qt.ItemDataRole.UserRole, path)
        for lineno, text in hits:
            child = QTreeWidgetItem([f"{lineno}: {text}"])
            child.setData(0, Qt.ItemDataRole.UserRole, path)
            child.setData(0, Qt.ItemDataRole.UserRole + 1, lineno)
            parent.addChild(child)
        self.results.addTopLevelItem(parent)
        parent.setExpanded(True)

    def _done(self, total: int, files: int) -> None:
        self.summary.setText(f"{total} in {files} file(s)")
        self._stop_running()

    def _stop_running(self) -> None:
        if self._worker is not None:
            self._worker.stop()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None

    def _activate(self, item: QTreeWidgetItem, _col: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        line = item.data(0, Qt.ItemDataRole.UserRole + 1) or 1
        if path:
            self.open_location.emit(path, int(line))
