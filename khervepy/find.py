"""Find & replace: an in-editor bar and a cross-file find/replace dialog.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Directories never worth searching.
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "env", ".env",
             "node_modules", ".idea", ".vscode", "build", "dist"}
# Only search files that look like text.
TEXT_EXTS = {
    ".py", ".pyw", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".c", ".h",
    ".cpp", ".cc", ".hpp", ".cs", ".java", ".go", ".rs", ".html", ".htm",
    ".css", ".scss", ".json", ".md", ".markdown", ".sh", ".bash", ".zsh",
    ".yml", ".yaml", ".sql", ".xml", ".txt", ".ini", ".cfg", ".toml", ".rst",
}


class FindBar(QWidget):
    """A slim find/replace bar that operates on the *current* editor.

    ``editor_getter`` is a callable returning the active ``CodeEditor`` (or
    ``None``). The bar drives QScintilla's own search so matches are
    highlighted and scrolled into view.
    """

    def __init__(self, editor_getter, parent=None):
        super().__init__(parent)
        self._get_editor = editor_getter
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 3, 6, 3)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.find_input.returnPressed.connect(self.find_next)
        self.find_input.textChanged.connect(self._reset_search)
        row.addWidget(self.find_input, 2)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace")
        self.replace_input.returnPressed.connect(self.replace_one)
        row.addWidget(self.replace_input, 2)

        self.case_cb = QCheckBox("Aa")
        self.case_cb.setToolTip("Case sensitive")
        self.word_cb = QCheckBox("W")
        self.word_cb.setToolTip("Whole word")
        self.regex_cb = QCheckBox(".*")
        self.regex_cb.setToolTip("Regular expression")
        for cb in (self.case_cb, self.word_cb, self.regex_cb):
            cb.toggled.connect(self._reset_search)
            row.addWidget(cb)

        prev_btn = QPushButton("◀")
        prev_btn.setToolTip("Find previous")
        prev_btn.clicked.connect(self.find_prev)
        next_btn = QPushButton("▶")
        next_btn.setToolTip("Find next")
        next_btn.clicked.connect(self.find_next)
        rep_btn = QPushButton("Replace")
        rep_btn.clicked.connect(self.replace_one)
        rep_all_btn = QPushButton("All")
        rep_all_btn.setToolTip("Replace all")
        rep_all_btn.clicked.connect(self.replace_all)
        close_btn = QPushButton("✕")
        close_btn.clicked.connect(self.hide)
        for b in (prev_btn, next_btn, rep_btn, rep_all_btn, close_btn):
            row.addWidget(b)

        self.status = QLabel("")
        row.addWidget(self.status)

    # --- behaviour -------------------------------------------------------
    def open(self, replace: bool = False) -> None:
        """Reveal the bar; pre-fill from the editor's current selection."""
        editor = self._get_editor()
        if editor is not None and editor.hasSelectedText():
            self.find_input.setText(editor.selectedText())
        self.replace_input.setVisible(replace)
        self.show()
        self.find_input.setFocus()
        self.find_input.selectAll()

    def _reset_search(self) -> None:
        self._active = False
        self.status.setText("")

    def _opts(self):
        return (
            self.regex_cb.isChecked(),
            self.case_cb.isChecked(),
            self.word_cb.isChecked(),
        )

    def find_next(self) -> None:
        self._find(forward=True)

    def find_prev(self) -> None:
        self._find(forward=False)

    def _find(self, forward: bool) -> None:
        editor = self._get_editor()
        text = self.find_input.text()
        if editor is None or not text:
            return
        regex, cs, wo = self._opts()
        if getattr(self, "_active", False):
            found = editor.findNext()
        else:
            found = editor.findFirst(text, regex, cs, wo, True, forward)
            self._active = found
        self.status.setText("" if found else "No matches")

    def replace_one(self) -> None:
        editor = self._get_editor()
        if editor is None:
            return
        if not getattr(self, "_active", False) or not editor.hasSelectedText():
            self._find(forward=True)
            return
        editor.replace(self.replace_input.text())
        self._find(forward=True)

    def replace_all(self) -> None:
        editor = self._get_editor()
        text = self.find_input.text()
        if editor is None or not text:
            return
        regex, cs, wo = self._opts()
        count = 0
        editor.beginUndoAction()
        found = editor.findFirst(text, regex, cs, wo, False, True, 0, 0)
        while found:
            editor.replace(self.replace_input.text())
            count += 1
            found = editor.findNext()
        editor.endUndoAction()
        self.status.setText(f"Replaced {count}")

    def keyPressEvent(self, event) -> None:  # Esc closes the bar.
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            editor = self._get_editor()
            if editor is not None:
                editor.setFocus()
            return
        super().keyPressEvent(event)


class FindInFilesDialog(QDialog):
    """Search — and optionally replace — across every text file in a project."""

    open_location = pyqtSignal(str, int)  # (path, line)

    def __init__(self, root: str, parent=None):
        super().__init__(parent)
        self.root = root
        self.setWindowTitle("Find / Replace in Files")
        self.resize(820, 560)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Search…")
        self.find_input.returnPressed.connect(self.search)
        row.addWidget(QLabel("Find:"))
        row.addWidget(self.find_input, 1)
        layout.addLayout(row)

        rrow = QHBoxLayout()
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replacement (optional)")
        rrow.addWidget(QLabel("Replace:"))
        rrow.addWidget(self.replace_input, 1)
        layout.addLayout(rrow)

        opts = QHBoxLayout()
        self.case_cb = QCheckBox("Case sensitive")
        self.word_cb = QCheckBox("Whole word")
        self.regex_cb = QCheckBox("Regex")
        opts.addWidget(self.case_cb)
        opts.addWidget(self.word_cb)
        opts.addWidget(self.regex_cb)
        opts.addStretch(1)
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search)
        self.replace_btn = QPushButton("Replace All in Files")
        self.replace_btn.clicked.connect(self.replace_all)
        opts.addWidget(self.search_btn)
        opts.addWidget(self.replace_btn)
        layout.addLayout(opts)

        self.results = QTreeWidget()
        self.results.setHeaderLabels(["File / match", "Line"])
        self.results.setColumnWidth(0, 640)
        self.results.itemDoubleClicked.connect(self._activate)
        layout.addWidget(self.results, 1)

        self.summary = QLabel("")
        layout.addWidget(self.summary)

    # --- searching -------------------------------------------------------
    def _pattern(self):
        text = self.find_input.text()
        if not text:
            return None
        flags = 0 if self.case_cb.isChecked() else re.IGNORECASE
        pat = text if self.regex_cb.isChecked() else re.escape(text)
        if self.word_cb.isChecked():
            pat = rf"\b{pat}\b"
        try:
            return re.compile(pat, flags)
        except re.error as exc:
            QMessageBox.warning(self, "Bad regex", str(exc))
            return None

    def _iter_files(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in TEXT_EXTS:
                    yield os.path.join(dirpath, fn)

    def search(self) -> None:
        rx = self._pattern()
        self.results.clear()
        if rx is None:
            return
        total, files = 0, 0
        for path in self._iter_files():
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            hits = [(i + 1, ln) for i, ln in enumerate(lines) if rx.search(ln)]
            if not hits:
                continue
            files += 1
            rel = os.path.relpath(path, self.root)
            parent = QTreeWidgetItem([f"{rel}  ({len(hits)})", ""])
            parent.setData(0, Qt.ItemDataRole.UserRole, path)
            for lineno, ln in hits:
                child = QTreeWidgetItem([ln.rstrip()[:200], str(lineno)])
                child.setData(0, Qt.ItemDataRole.UserRole, path)
                child.setData(1, Qt.ItemDataRole.UserRole, lineno)
                parent.addChild(child)
                total += 1
            self.results.addTopLevelItem(parent)
            parent.setExpanded(True)
        self.summary.setText(f"{total} match(es) in {files} file(s)")

    def replace_all(self) -> None:
        rx = self._pattern()
        if rx is None:
            return
        replacement = self.replace_input.text()
        answer = QMessageBox.question(
            self, "Replace in files",
            f"Replace all matches of “{self.find_input.text()}” with "
            f"“{replacement}” across the project?\nThis rewrites files on disk.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        changed_files, changed = 0, 0
        for path in self._iter_files():
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue
            new_content, n = rx.subn(replacement, content)
            if n:
                # Preserve UTF-8 + \n line endings (never mangle user data).
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(new_content)
                changed_files += 1
                changed += n
        self.summary.setText(f"Replaced {changed} match(es) in {changed_files} file(s)")
        self.search()

    def _activate(self, item: QTreeWidgetItem, _col: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        line = item.data(1, Qt.ItemDataRole.UserRole) or 1
        if path:
            self.open_location.emit(path, int(line))
