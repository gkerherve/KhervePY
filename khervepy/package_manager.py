"""Virtual-environment and package management dialog.

Lets the user create/select virtual environments and pip-install packages
without leaving the editor. All heavy work runs on a worker thread and streams
output into a log pane.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt6.QtCore import QObject, QProcess, Qt

from khervepy.proc import hide_console, python_executable, subprocess_flags
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _python_in(venv_dir: str) -> str:
    """Return the interpreter path inside a virtual environment."""
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


class PackageManager(QDialog):
    """Environment + package management UI."""

    def __init__(self, project_root: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KhervePY — Environments & Packages")
        self.resize(720, 560)
        self.project_root = project_root or os.getcwd()
        self._proc: QProcess | None = None

        self._build_ui()
        self._discover_envs()

    # --- UI --------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Environment selector.
        env_row = QHBoxLayout()
        env_row.addWidget(QLabel("Environment:"))
        self.env_box = QComboBox()
        self.env_box.currentIndexChanged.connect(self._refresh_packages)
        env_row.addWidget(self.env_box, 1)
        self.create_btn = QPushButton("Create venv…")
        self.create_btn.clicked.connect(self._create_env)
        env_row.addWidget(self.create_btn)
        self.add_existing_btn = QPushButton("Add existing…")
        self.add_existing_btn.clicked.connect(self._add_existing_env)
        env_row.addWidget(self.add_existing_btn)
        layout.addLayout(env_row)

        # Installed packages.
        layout.addWidget(QLabel("Installed packages"))
        self.pkg_list = QListWidget()
        layout.addWidget(self.pkg_list, 1)

        # Install row.
        install_row = QHBoxLayout()
        self.pkg_input = QLineEdit()
        self.pkg_input.setPlaceholderText("package name(s), e.g. numpy pandas requests")
        self.pkg_input.returnPressed.connect(self._install)
        install_row.addWidget(self.pkg_input, 1)
        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self._install)
        install_row.addWidget(self.install_btn)
        self.uninstall_btn = QPushButton("Uninstall selected")
        self.uninstall_btn.clicked.connect(self._uninstall)
        install_row.addWidget(self.uninstall_btn)
        layout.addLayout(install_row)

        # Requirements convenience.
        req_row = QHBoxLayout()
        self.req_btn = QPushButton("Install requirements.txt…")
        self.req_btn.clicked.connect(self._install_requirements)
        self.freeze_btn = QPushButton("Freeze → requirements.txt")
        self.freeze_btn.clicked.connect(self._freeze)
        req_row.addWidget(self.req_btn)
        req_row.addWidget(self.freeze_btn)
        layout.addLayout(req_row)

        # Log.
        layout.addWidget(QLabel("Output"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleHint = None
        layout.addWidget(self.log, 1)

    # --- environment discovery ------------------------------------------
    def _discover_envs(self) -> None:
        """Populate the selector with the base interpreter + local venvs."""
        self.env_box.blockSignals(True)
        self.env_box.clear()
        system_py = python_executable(self.project_root) or sys.executable
        self.env_box.addItem(f"System ({system_py})", system_py)

        for name in ("venv", ".venv", "env", ".env"):
            candidate = os.path.join(self.project_root, name)
            py = _python_in(candidate)
            if os.path.isfile(py):
                self.env_box.addItem(f"{name} ({py})", py)

        self.env_box.blockSignals(False)
        self._refresh_packages()

    def current_python(self) -> str:
        return self.env_box.currentData() or sys.executable

    def _add_existing_env(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select a virtualenv folder", self.project_root
        )
        if not folder:
            return
        py = _python_in(folder)
        if not os.path.isfile(py):
            QMessageBox.warning(self, "Not a venv", "No interpreter found there.")
            return
        self.env_box.addItem(f"{os.path.basename(folder)} ({py})", py)
        self.env_box.setCurrentIndex(self.env_box.count() - 1)

    def _create_env(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Create virtual environment", "Folder name:", text=".venv"
        )
        if not ok or not name.strip():
            return
        target = os.path.join(self.project_root, name.strip())
        self._append(f"$ {sys.executable} -m venv {target}\n")
        try:
            subprocess.run(
                [python_executable(self.project_root) or sys.executable,
                 "-m", "venv", target],
                check=True, capture_output=True, text=True, **subprocess_flags(),
            )
        except subprocess.CalledProcessError as exc:
            self._append(exc.stderr or "venv creation failed\n")
            return
        self._append("Environment created.\n")
        self._discover_envs()
        idx = self.env_box.findData(_python_in(target))
        if idx >= 0:
            self.env_box.setCurrentIndex(idx)

    # --- pip operations (streamed via QProcess) --------------------------
    def _run_pip(self, args: list[str]) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Busy", "A pip command is already running.")
            return
        py = self.current_python()
        self._append(f"$ {py} -m pip {' '.join(args)}\n")
        self._set_busy(True)

        self._proc = QProcess(self)
        hide_console(self._proc)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_proc)
        self._proc.finished.connect(self._pip_finished)
        self._proc.start(py, ["-m", "pip", *args])

    def _read_proc(self) -> None:
        if self._proc:
            data = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
            self._append(data)

    def _pip_finished(self, code: int, _status) -> None:
        self._append(f"\n[pip exited with code {code}]\n")
        self._set_busy(False)
        self._refresh_packages()

    def _install(self) -> None:
        pkgs = self.pkg_input.text().split()
        if not pkgs:
            return
        self._run_pip(["install", *pkgs])
        self.pkg_input.clear()

    def _uninstall(self) -> None:
        items = [i.text().split("==")[0] for i in self.pkg_list.selectedItems()]
        if not items:
            return
        self._run_pip(["uninstall", "-y", *items])

    def _install_requirements(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose requirements file", self.project_root,
            "Requirements (*.txt);;All files (*)",
        )
        if path:
            self._run_pip(["install", "-r", path])

    def _freeze(self) -> None:
        py = self.current_python()
        try:
            out = subprocess.run(
                [py, "-m", "pip", "freeze"],
                capture_output=True, text=True, check=True, **subprocess_flags(),
            ).stdout
        except subprocess.CalledProcessError as exc:
            self._append(exc.stderr or "freeze failed\n")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save requirements", os.path.join(self.project_root, "requirements.txt"),
            "Requirements (*.txt)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(out)
            self._append(f"Wrote {path}\n")

    def _refresh_packages(self) -> None:
        self.pkg_list.clear()
        py = self.current_python()
        try:
            out = subprocess.run(
                [py, "-m", "pip", "list", "--format=freeze"],
                capture_output=True, text=True, timeout=30, **subprocess_flags(),
            ).stdout
        except (subprocess.SubprocessError, OSError):
            return
        for line in out.splitlines():
            if line.strip():
                self.pkg_list.addItem(line.strip())

    # --- helpers ---------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        for w in (self.install_btn, self.uninstall_btn, self.req_btn,
                  self.freeze_btn, self.create_btn):
            w.setEnabled(not busy)

    def _append(self, text: str) -> None:
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)
        self.log.insertPlainText(text)
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)
