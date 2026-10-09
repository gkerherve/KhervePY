"""Dialogs for choosing an interpreter and editing run configurations.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from khervepy import proc
from khervepy.run_config import CURRENT_FILE, KINDS, RUN_TESTS, RunConfig

_AUTO = "Automatic — the project's virtualenv, else the system Python"


class _LabelWorker(QThread):
    """Names the interpreters off the GUI thread (``python --version`` is slow)."""

    found = pyqtSignal(str, str)     # path, label
    finished_all = pyqtSignal()

    def __init__(self, paths: list[str], project_root: str, parent=None):
        super().__init__(parent)
        self._paths = paths
        self._root = project_root

    def run(self) -> None:
        for path in self._paths:
            self.found.emit(path, proc.interpreter_label(path, self._root))
        self.finished_all.emit()


class InterpreterDialog(QDialog):
    """Pick the Python a project runs, debugs and pip-installs with."""

    def __init__(self, project_root: str, current: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Python Interpreter")
        self.resize(640, 420)
        self._root = project_root
        self._current = current
        self._items: dict[str, QListWidgetItem] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Interpreter for <b>{os.path.basename(project_root) or project_root}</b>"
            " — used by Run, Debug and Packages."))
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        layout.addWidget(self.list, 1)

        auto = QListWidgetItem(_AUTO)
        auto.setData(Qt.ItemDataRole.UserRole, "")
        self.list.addItem(auto)
        if not current:
            self.list.setCurrentItem(auto)

        self.status = QLabel("Looking for interpreters…")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        layout.addLayout(row)

        paths = proc.interpreter_candidates(project_root)
        if current and current not in paths and os.path.isfile(current):
            paths.insert(0, current)
        for path in paths:
            self._add(path, path)
        self._worker = _LabelWorker(paths, project_root, self)
        self._worker.found.connect(self._relabel)
        self._worker.finished_all.connect(self._done)
        self._worker.start()

    def _add(self, path: str, text: str) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(path)
        self.list.addItem(item)
        self._items[path] = item
        if path == self._current:
            self.list.setCurrentItem(item)
        return item

    def _relabel(self, path: str, label: str) -> None:
        item = self._items.get(path)
        if item is None:
            return
        if label.startswith("Python ?"):          # a wrapper that is not a Python
            self.list.takeItem(self.list.row(item))
            del self._items[path]
            return
        item.setText(f"{label}\n    {path}")

    def _done(self) -> None:
        self.status.setText(f"{len(self._items)} interpreter(s) found.")

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a Python interpreter")
        if not path:
            return
        item = self._items.get(path) or self._add(path, path)
        self.list.setCurrentItem(item)
        self._relabel(path, proc.interpreter_label(path, self._root))

    def selected(self) -> str:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else self._current

    def done(self, result: int) -> None:
        self._worker.wait(2000)
        super().done(result)


class RunConfigDialog(QDialog):
    """Create, edit, duplicate and delete a project's run configurations."""

    def __init__(self, project_root: str, configs: list[RunConfig],
                 selected: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Run Configurations")
        self.resize(780, 520)
        self._root = project_root
        self._configs = [RunConfig.from_dict(c.to_dict()) for c in configs]
        self._row = -1

        outer = QHBoxLayout(self)

        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumWidth(230)
        self.list.currentRowChanged.connect(self._select)
        left.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, slot in (("+", self._add), ("Copy", self._duplicate), ("–", self._remove)):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        self.remove_btn = row.itemAt(2).widget()
        left.addLayout(row)
        outer.addLayout(left)

        right = QVBoxLayout()
        form = QFormLayout()
        self.name = QLineEdit()
        self.kind = QComboBox()
        self.kind.addItems(["Script (.py file)", "Module (python -m)", "pytest"])
        self.target = QLineEdit()
        self.target_btn = QPushButton("…")
        self.target_btn.setFixedWidth(32)
        self.target_btn.clicked.connect(self._browse_target)
        target_row = QHBoxLayout()
        target_row.addWidget(self.target, 1)
        target_row.addWidget(self.target_btn)
        self.args = QLineEdit()
        self.args.setPlaceholderText('e.g. --epochs 5 "my file.csv"   ($FILE, $FILEDIR, $PROJECT)')
        self.cwd = QLineEdit()
        self.cwd.setPlaceholderText("blank = project folder")
        self.interp = QLineEdit()
        self.interp.setPlaceholderText("blank = the project's interpreter")
        self.env = QPlainTextEdit()
        self.env.setPlaceholderText("one per line:\nDEBUG=1\nDATA_DIR=$PROJECT/data")
        self.env.setFixedHeight(90)
        self.in_terminal = QCheckBox("Run in the Terminal (keyboard input, colours, Ctrl-C)")
        self.hint = QLabel()
        self.hint.setWordWrap(True)

        form.addRow("Name", self.name)
        form.addRow("Type", self.kind)
        self.target_label = QLabel("Script")
        form.addRow(self.target_label, target_row)
        form.addRow("Arguments", self.args)
        form.addRow("Working dir", self.cwd)
        form.addRow("Interpreter", self.interp)
        form.addRow("Environment", self.env)
        form.addRow("", self.in_terminal)
        right.addLayout(form)
        right.addWidget(self.hint)
        right.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)
        outer.addLayout(right, 1)

        self.kind.currentIndexChanged.connect(self._kind_changed)
        start = 0
        for i, cfg in enumerate(self._configs):
            self.list.addItem(cfg.name)
            if cfg.name == selected:
                start = i
        self.list.setCurrentRow(start)

    # --- list actions ---------------------------------------------------------
    def _is_builtin(self, cfg: RunConfig) -> bool:
        return cfg.name in (CURRENT_FILE, RUN_TESTS)

    def _unique(self, base: str) -> str:
        names = {c.name for c in self._configs}
        name, n = base, 2
        while name in names:
            name, n = f"{base} {n}", n + 1
        return name

    def _add(self) -> None:
        self._store()
        cfg = RunConfig(self._unique("New configuration"))
        self._configs.append(cfg)
        self.list.addItem(cfg.name)
        self.list.setCurrentRow(len(self._configs) - 1)

    def _duplicate(self) -> None:
        self._store()
        if self._row < 0:
            return
        cfg = RunConfig.from_dict(self._configs[self._row].to_dict())
        cfg.name = self._unique(cfg.name + " copy")
        self._configs.append(cfg)
        self.list.addItem(cfg.name)
        self.list.setCurrentRow(len(self._configs) - 1)

    def _remove(self) -> None:
        if self._row < 0 or self._is_builtin(self._configs[self._row]):
            return
        row = self._row
        self._row = -1
        del self._configs[row]
        self.list.takeItem(row)
        self.list.setCurrentRow(min(row, len(self._configs) - 1))

    # --- form <-> config -------------------------------------------------------
    def _select(self, row: int) -> None:
        self._store()
        self._row = row
        if row < 0:
            return
        cfg = self._configs[row]
        builtin = self._is_builtin(cfg)
        self.name.setEnabled(not builtin)
        self.remove_btn.setEnabled(not builtin)
        self.kind.setEnabled(not builtin)
        self.name.setText(cfg.name)
        self.kind.blockSignals(True)
        self.kind.setCurrentIndex(KINDS.index(cfg.kind))
        self.kind.blockSignals(False)
        self.target.setText(cfg.target)
        self.args.setText(cfg.args)
        self.cwd.setText(cfg.cwd)
        self.interp.setText(cfg.interpreter)
        self.env.setPlainText(cfg.env)
        self.in_terminal.setChecked(cfg.in_terminal)
        self.target.setEnabled(cfg.name != CURRENT_FILE)
        self.target_btn.setEnabled(cfg.name != CURRENT_FILE)
        self._kind_changed()

    def _kind_changed(self) -> None:
        kind = KINDS[self.kind.currentIndex()]
        label, hint = {
            "script": ("Script", "Runs the file with <code>python -u</code>. "
                                 "Leave Script empty to run the file in the active tab."),
            "module": ("Module", "Runs <code>python -u -m &lt;module&gt;</code>, e.g. "
                                 "<code>http.server</code> or <code>mypkg.cli</code>."),
            "pytest": ("Tests", "Runs <code>python -m pytest</code>. Leave empty for the whole "
                                "project, or give a path / node id such as "
                                "<code>tests/test_x.py::test_y</code>."),
        }[kind]
        self.target_label.setText(label)
        self.hint.setText(hint)
        self.target_btn.setVisible(kind != "module")

    def _store(self) -> None:
        if not (0 <= self._row < len(self._configs)):
            return
        cfg = self._configs[self._row]
        if not self._is_builtin(cfg):
            new = self.name.text().strip() or cfg.name
            if new != cfg.name and new not in {c.name for c in self._configs}:
                cfg.name = new
                self.list.item(self._row).setText(new)
            cfg.kind = KINDS[self.kind.currentIndex()]
        if cfg.name != CURRENT_FILE:
            cfg.target = self.target.text().strip()
        cfg.args = self.args.text().strip()
        cfg.cwd = self.cwd.text().strip()
        cfg.interpreter = self.interp.text().strip()
        cfg.env = self.env.toPlainText().strip()
        cfg.in_terminal = self.in_terminal.isChecked()

    def _browse_target(self) -> None:
        kind = KINDS[self.kind.currentIndex()]
        if kind == "pytest":
            path, _ = QFileDialog.getOpenFileName(self, "Choose a test file", self._root,
                                                  "Python (*.py)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Choose a script", self._root,
                                                  "Python (*.py *.pyw)")
        if path:
            try:
                rel = os.path.relpath(path, self._root)
                path = rel if not rel.startswith("..") else path
            except ValueError:
                pass
            self.target.setText(path)

    def _save(self) -> None:
        self._store()
        for cfg in self._configs:
            if cfg.kind == "module" and not cfg.target.strip():
                QMessageBox.warning(self, "Run Configurations",
                                    f"“{cfg.name}” is a module configuration but has no module.")
                return
        self.accept()

    def configs(self) -> list[RunConfig]:
        return self._configs

    def selected_name(self) -> str:
        return self._configs[self._row].name if 0 <= self._row < len(self._configs) else CURRENT_FILE
