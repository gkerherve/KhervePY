"""A colourised unified-diff viewer for the Git panel.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class _DiffHighlighter(QSyntaxHighlighter):
    """Colours added/removed lines and hunk headers of a unified diff."""

    def __init__(self, document):
        super().__init__(document)
        self._added = self._fmt("#3FB950")
        self._removed = self._fmt("#F85149")
        self._hunk = self._fmt("#58A6FF", bold=True)
        self._meta = self._fmt("#8B949E")

    @staticmethod
    def _fmt(color: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt

    def highlightBlock(self, text: str) -> None:
        if not text:
            return
        if text.startswith("@@"):
            self.setFormat(0, len(text), self._hunk)
        elif text.startswith("+++") or text.startswith("---") \
                or text.startswith("diff ") or text.startswith("index ") \
                or text.startswith("new file") or text.startswith("deleted"):
            self.setFormat(0, len(text), self._meta)
        elif text.startswith("+"):
            self.setFormat(0, len(text), self._added)
        elif text.startswith("-"):
            self.setFormat(0, len(text), self._removed)


class DiffViewer(QWidget):
    """Shows the unified diff of a single file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.header = QLabel("Select a changed file in the Git panel.")
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        mono = QFont("Consolas, DejaVu Sans Mono, Menlo, monospace", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(mono)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._highlighter = _DiffHighlighter(self.view.document())
        layout.addWidget(self.view, 1)

    def show_diff(self, title: str, text: str) -> None:
        self.header.setText(title)
        self.view.setPlainText(text or "(no changes to show)")
