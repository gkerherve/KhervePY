"""An integrated terminal dock backed by a persistent shell process.

This is a line-oriented terminal (a real PTY is out of scope for a lightweight
IDE): it runs an interactive shell via ``QProcess`` and pipes typed commands to
its stdin, streaming merged stdout/stderr into the same view. Standard
commands, git, pip and scripts work; full-screen/curses programs do not.

You type directly into the console view, as in a real terminal: text is
editable only after the point where the shell's last output ended, so the
scrollback cannot be clobbered.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QFont, QKeyEvent, QKeySequence, QTextCursor
from PyQt6.QtCore import Qt

from khervepy.proc import hide_console
from PyQt6.QtWidgets import (
    QHBoxLayout,
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


class _Console(QPlainTextEdit):
    """An editable console view: shell output plus an inline input zone.

    Everything before ``_input_anchor`` is scrollback and is protected from
    editing; everything after it is what the user is currently typing. The
    anchor is stored as an offset into the *last* block rather than an absolute
    document position, so trimming old scrollback (``maximumBlockCount``) cannot
    invalidate it.
    """

    def __init__(self, on_submit):
        super().__init__()
        self._on_submit = on_submit
        self._history: list[str] = []
        self._index = 0
        self._input_col = 0
        self.setUndoRedoEnabled(False)
        self.setMaximumBlockCount(5000)  # cap scrollback

    # --- the input zone ---------------------------------------------------
    def _input_pos(self) -> int:
        """Absolute document position where the editable input begins."""
        last = self.document().lastBlock()
        return last.position() + min(self._input_col, len(last.text()))

    def input_text(self) -> str:
        return self.toPlainText()[self._input_pos():]

    def _set_input(self, text: str) -> None:
        cursor = self.textCursor()
        cursor.setPosition(self._input_pos())
        cursor.movePosition(QTextCursor.MoveOperation.End,
                            QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text)  # replaces the selection
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_output(self, text: str) -> None:
        """Insert shell output, preserving any half-typed input after it."""
        pending = self.input_text()
        if pending:
            self._set_input("")
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._input_col = len(self.document().lastBlock().text())
        if pending:
            cursor.insertText(pending)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def clear_all(self) -> None:
        self.clear()
        self._input_col = 0

    # --- key handling -----------------------------------------------------
    def _submit(self) -> None:
        text = self.input_text()
        if text.strip():
            self._history.append(text)
        self._index = len(self._history)
        # Retire the typed line into the scrollback: break the line and start a
        # fresh, empty input zone. (append_output would treat the text as
        # still-pending input and carry it across the newline.)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n")
        self._input_col = 0
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self._on_submit(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        cursor = self.textCursor()
        start = self._input_pos()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._submit()
            return
        if key == Qt.Key.Key_Up and self._history:
            self._index = max(0, self._index - 1)
            self._set_input(self._history[self._index])
            return
        if key == Qt.Key.Key_Down and self._history:
            self._index = min(len(self._history), self._index + 1)
            self._set_input(self._history[self._index]
                            if self._index < len(self._history) else "")
            return
        if key == Qt.Key.Key_Home:
            cursor.setPosition(start)
            self.setTextCursor(cursor)
            return

        # Let copy and the navigation keys roam the scrollback freely.
        if event.matches(QKeySequence.StandardKey.Copy) or key in (
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_End,
            Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
        ):
            super().keyPressEvent(event)
            return

        # Anything that edits must happen inside the input zone: pull the
        # cursor back to the end if the user clicked into the scrollback.
        if cursor.position() < start or cursor.selectionStart() < start:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
        if key == Qt.Key.Key_Backspace and self.textCursor().position() <= start:
            return  # don't chew into the prompt
        super().keyPressEvent(event)


class Terminal(QWidget):
    """Persistent shell in a dockable widget."""

    def __init__(self, cwd: str | None = None, parent=None):
        super().__init__(parent)
        self.cwd = cwd or os.getcwd()
        self._proc: QProcess | None = None
        self._pending_echo: str | None = None
        self._build_ui()
        self.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)

        self.view = _Console(self.send_command)
        self.view.setFont(mono)
        layout.addWidget(self.view, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.view.clear_all)
        restart_btn = QPushButton("Restart")
        restart_btn.clicked.connect(self.restart)
        row.addWidget(clear_btn)
        row.addWidget(restart_btn)
        layout.addLayout(row)

        # Typing anywhere in the dock lands in the console.
        self.setFocusProxy(self.view)

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
        self.view.append_output(f"[started {program} in {self.cwd}]\n")

    def restart(self) -> None:
        self.stop()
        self.view.clear_all()
        self.start()

    def stop(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(1500)

    def set_cwd(self, path: str) -> None:
        """Follow the active project by changing directory in the live shell."""
        self.cwd = path
        if self._proc is not None and self._proc.state() == QProcess.ProcessState.Running:
            self.send_command(f"cd {self._quote(path)}", echo=True)
        else:
            self.restart()

    # --- io --------------------------------------------------------------
    def send_command(self, text: str, echo: bool = False) -> None:
        """Write ``text`` to the shell's stdin.

        ``echo`` shows the command in the view first; it is only needed for
        commands KhervePY issues itself (the user's own typing is already on
        screen).
        """
        if self._proc is None or self._proc.state() != QProcess.ProcessState.Running:
            self.start()
        if echo:
            self.view.append_output(f"{text}\n")
        # The shell echoes back what it reads from the pipe; that would double
        # up the text already on screen, so drop the first echoed copy.
        self._pending_echo = text
        self._proc.write((text + "\n").encode())

    def _read(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        data = self._strip_echo(data)
        if data:
            self.view.append_output(data)

    def _strip_echo(self, data: str) -> str:
        """Remove the shell's echo of the command we just sent, once."""
        pending, self._pending_echo = self._pending_echo, None
        if not pending:
            return data
        for newline in ("\r\n", "\n"):
            prefix = pending + newline
            if data.startswith(prefix):
                return data[len(prefix):]
        # Echo not in this chunk (or the child doesn't echo): leave it alone.
        self._pending_echo = pending if not data.strip() else None
        return data

    def _on_finished(self, code: int, _status) -> None:
        self.view.append_output(f"\n[shell exited with code {code}] — press Restart]\n")

    def _on_error(self, _err) -> None:
        if self._proc is not None:
            self.view.append_output(f"\n[terminal error: {self._proc.errorString()}]\n")

    @staticmethod
    def _quote(path: str) -> str:
        if os.name == "nt":
            return f'"{path}"'
        return "'" + path.replace("'", "'\\''") + "'"
