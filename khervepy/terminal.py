"""An integrated terminal dock backed by a persistent shell process.

This is a line-oriented terminal (a real PTY is out of scope for a lightweight
IDE): it runs an interactive shell via ``QProcess`` and pipes typed commands to
its stdin, streaming merged stdout/stderr into a read-only view. Standard
commands, git, pip and scripts work; full-screen/curses programs do not.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtCore import Qt

from khervepy.proc import hide_console
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _default_shell() -> tuple[str, list[str]]:
    """Return ``(program, args)`` for the platform's interactive shell."""
    if os.name == "nt":
        return os.environ.get("COMSPEC", "cmd.exe"), []
    shell = os.environ.get("SHELL", "/bin/bash")
    # -i keeps it interactive; most shells accept it.
    return shell, ["-i"]


class _CommandLine(QLineEdit):
    """A line edit with up/down shell-style history."""

    def __init__(self, on_submit):
        super().__init__()
        self._on_submit = on_submit
        self._history: list[str] = []
        self._index = 0
        self.returnPressed.connect(self._submit)
        self.setPlaceholderText("Type a command and press Enter…")

    def _submit(self) -> None:
        text = self.text()
        if text.strip():
            self._history.append(text)
        self._index = len(self._history)
        self._on_submit(text)
        self.clear()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Up and self._history:
            self._index = max(0, self._index - 1)
            self.setText(self._history[self._index])
            return
        if event.key() == Qt.Key.Key_Down and self._history:
            self._index = min(len(self._history), self._index + 1)
            self.setText(self._history[self._index] if self._index < len(self._history) else "")
            return
        super().keyPressEvent(event)


class Terminal(QWidget):
    """Persistent shell in a dockable widget."""

    def __init__(self, cwd: str | None = None, parent=None):
        super().__init__(parent)
        self.cwd = cwd or os.getcwd()
        self._proc: QProcess | None = None
        self._build_ui()
        self.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        mono = QFont("Consolas, DejaVu Sans Mono, Menlo, monospace", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(mono)
        self.view.setMaximumBlockCount(5000)  # cap scrollback
        layout.addWidget(self.view, 1)

        row = QHBoxLayout()
        self.prompt = QLabel("$")
        row.addWidget(self.prompt)
        self.input = _CommandLine(self.send_command)
        self.input.setFont(mono)
        self.input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        row.addWidget(self.input, 1)

        # The output view is read-only, so clicking it would otherwise swallow
        # focus and typing would go nowhere. Route focus (and therefore keys)
        # to the command line, from both the view and the dock itself, while
        # leaving the view's mouse handling intact for selecting text.
        self.view.setFocusProxy(self.input)
        self.setFocusProxy(self.input)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.view.clear)
        restart_btn = QPushButton("Restart")
        restart_btn.clicked.connect(self.restart)
        row.addWidget(clear_btn)
        row.addWidget(restart_btn)
        layout.addLayout(row)

    # --- process management ----------------------------------------------
    def start(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            return
        program, args = _default_shell()
        self._proc = QProcess(self)
        hide_console(self._proc)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.setWorkingDirectory(self.cwd)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)
        self._proc.start(program, args)
        self._append(f"[started {program} in {self.cwd}]\n")

    def restart(self) -> None:
        self.stop()
        self.view.clear()
        self.start()

    def stop(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(1500)

    def set_cwd(self, path: str) -> None:
        """Follow the active project by changing directory in the live shell."""
        self.cwd = path
        if self._proc is not None and self._proc.state() == QProcess.ProcessState.Running:
            self.send_command(f"cd {self._quote(path)}", echo=False)
        else:
            self.restart()

    # --- io --------------------------------------------------------------
    def send_command(self, text: str, echo: bool = True) -> None:
        if self._proc is None or self._proc.state() != QProcess.ProcessState.Running:
            self.start()
        if echo:
            self._append(f"$ {text}\n")
        self._proc.write((text + "\n").encode())

    def _read(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        self._append(data)

    def _on_finished(self, code: int, _status) -> None:
        self._append(f"\n[shell exited with code {code}] — press Restart]\n")

    def _on_error(self, _err) -> None:
        if self._proc is not None:
            self._append(f"\n[terminal error: {self._proc.errorString()}]\n")

    def _append(self, text: str) -> None:
        self.view.moveCursor(self.view.textCursor().MoveOperation.End)
        self.view.insertPlainText(text)
        self.view.moveCursor(self.view.textCursor().MoveOperation.End)

    @staticmethod
    def _quote(path: str) -> str:
        if os.name == "nt":
            return f'"{path}"'
        return "'" + path.replace("'", "'\\''") + "'"
