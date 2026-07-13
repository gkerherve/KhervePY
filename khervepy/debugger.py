"""A lightweight Python debugger dock driven by the standard-library ``pdb``.

The current file is run under ``python -u -m pdb`` in a ``QProcess``; the panel
exposes the usual controls (continue, step, next, return, quit), lets you set a
breakpoint at the current editor line, and offers a raw pdb command line. It is
deliberately simple — no variable-inspection tree — but covers stepping and
breakpoints without leaving the editor.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Debugger(QWidget):
    """Drive ``pdb`` over stdin/stdout inside a dock.

    ``location_getter`` returns ``(path, line)`` for the current editor so the
    "Break here" button can set a breakpoint at the caret.
    """

    def __init__(self, location_getter, cwd: str | None = None, parent=None):
        super().__init__(parent)
        self._get_location = location_getter
        self.cwd = cwd or os.getcwd()
        self._proc: QProcess | None = None
        self._build_ui()
        self._set_running(False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # Control row.
        controls = QHBoxLayout()
        self.start_btn = QPushButton("▶ Debug file")
        self.start_btn.clicked.connect(self.start_current)
        controls.addWidget(self.start_btn)

        self.cont_btn = self._cmd_button(controls, "Continue", "continue")
        self.step_btn = self._cmd_button(controls, "Step", "step")
        self.next_btn = self._cmd_button(controls, "Next", "next")
        self.ret_btn = self._cmd_button(controls, "Return", "return")

        self.break_btn = QPushButton("Break here")
        self.break_btn.clicked.connect(self.break_at_current)
        controls.addWidget(self.break_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop)
        controls.addWidget(self.stop_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        mono = QFont("Consolas, DejaVu Sans Mono, Menlo, monospace", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(mono)
        self.view.setMaximumBlockCount(5000)
        layout.addWidget(self.view, 1)

        row = QHBoxLayout()
        row.addWidget(QLabel("(Pdb)"))
        self.input = QLineEdit()
        self.input.setFont(mono)
        self.input.setPlaceholderText("pdb command, e.g. p my_var, l, w, b 12…")
        self.input.returnPressed.connect(self._send_input)
        row.addWidget(self.input, 1)
        layout.addLayout(row)

    def _cmd_button(self, layout, label: str, command: str) -> QPushButton:
        btn = QPushButton(label)
        btn.clicked.connect(lambda: self.send(command))
        layout.addWidget(btn)
        return btn

    # --- lifecycle -------------------------------------------------------
    def set_cwd(self, path: str) -> None:
        self.cwd = path

    def start(self, path: str) -> None:
        if not path or not path.endswith(".py"):
            self._append("[Debugger runs .py files only]\n")
            return
        self.stop()
        self.view.clear()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.setWorkingDirectory(self.cwd)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._on_finished)
        self._proc.start(sys.executable, ["-u", "-m", "pdb", path])
        self._append(f"[pdb {os.path.basename(path)}]\n")
        self._set_running(True)

    def start_current(self) -> None:
        path, _line = self._get_location()
        self.start(path)

    def stop(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self.send("quit")
            self._proc.kill()
            self._proc.waitForFinished(1000)
        self._set_running(False)

    def _on_finished(self, code: int, _status) -> None:
        self._append(f"\n[debugger exited with code {code}]\n")
        self._set_running(False)

    # --- commands --------------------------------------------------------
    def send(self, command: str) -> None:
        if self._proc is None or self._proc.state() != QProcess.ProcessState.Running:
            self._append("[no debug session — press Debug file]\n")
            return
        self._append(f"(Pdb) {command}\n")
        self._proc.write((command + "\n").encode())

    def _send_input(self) -> None:
        text = self.input.text()
        self.input.clear()
        if text.strip():
            self.send(text)

    def break_at_current(self) -> None:
        path, line = self._get_location()
        if not path:
            return
        if self._proc is None or self._proc.state() != QProcess.ProcessState.Running:
            self._append(f"[start a debug session, then break at {os.path.basename(path)}:{line}]\n")
            return
        self.send(f"break {path}:{line}")

    # --- io --------------------------------------------------------------
    def _read(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        self._append(data)

    def _append(self, text: str) -> None:
        self.view.moveCursor(self.view.textCursor().MoveOperation.End)
        self.view.insertPlainText(text)
        self.view.moveCursor(self.view.textCursor().MoveOperation.End)

    def _set_running(self, running: bool) -> None:
        for b in (self.cont_btn, self.step_btn, self.next_btn, self.ret_btn,
                  self.stop_btn, self.input):
            b.setEnabled(running)
        self.break_btn.setEnabled(True)
        self.start_btn.setEnabled(not running)
