"""The code-editor widget: a configured ``QsciScintilla`` instance.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics
from PyQt6.Qsci import QsciScintilla

from khervepy.lexers import make_lexer
from khervepy.themes import THEMES, DEFAULT_THEME, apply_theme


class CodeEditor(QsciScintilla):
    """A single editable buffer, theme-aware and language-aware."""

    def __init__(self, path: str | None = None, font_size: int = 11, parent=None):
        super().__init__(parent)
        self.path = path
        self._lexer = None
        self._font = QFont("Consolas, DejaVu Sans Mono, Menlo, monospace", font_size)
        self._font.setStyleHint(QFont.StyleHint.Monospace)

        self._configure_editor()
        if path and os.path.isfile(path):
            self._load(path)
        self.set_lexer_for_path(path or "")
        self.apply_theme(DEFAULT_THEME)

    # --- setup -----------------------------------------------------------
    def _configure_editor(self) -> None:
        self.setUtf8(True)
        self.setFont(self._font)

        # Line-number margin, sized to content.
        self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.setMarginLineNumbers(0, True)
        self._resize_line_margin()

        # Fold margin.
        self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle, 2)

        # Editing behaviour.
        self.setAutoIndent(True)
        self.setIndentationsUseTabs(False)
        self.setTabWidth(4)
        self.setIndentationGuides(True)
        self.setBackspaceUnindents(True)
        self.setCaretLineVisible(True)
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setWrapMode(QsciScintilla.WrapMode.WrapNone)
        self.setEolMode(QsciScintilla.EolMode.EolUnix)

        # Autocompletion from the document itself.
        self.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
        self.setAutoCompletionThreshold(2)
        self.setAutoCompletionCaseSensitivity(False)

        # A right margin marker at column 88 (black default).
        self.setEdgeMode(QsciScintilla.EdgeMode.EdgeLine)
        self.setEdgeColumn(88)

    def _resize_line_margin(self) -> None:
        metrics = QFontMetrics(self._font)
        digits = max(2, len(str(max(1, self.lines()))))
        self.setMarginWidth(0, metrics.horizontalAdvance("9") * (digits + 1) + 6)

    def _load(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                self.setText(fh.read())
        except OSError:
            self.setText("")
        self.setModified(False)
        self._resize_line_margin()

    # --- language & theme ------------------------------------------------
    def set_lexer_for_path(self, path: str) -> None:
        self._lexer = make_lexer(path) if path else None
        if self._lexer is not None:
            self._lexer.setDefaultFont(self._font)
            self._lexer.setFont(self._font)
        self.setLexer(self._lexer)

    def apply_theme(self, theme_name: str) -> None:
        theme = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
        if self._lexer is not None:
            self._lexer.setDefaultFont(self._font)
        apply_theme(self, self._lexer, theme)
        self.setEdgeColor(QColor(theme.margin_fg))
        self.setMarginsFont(self._font)

    def set_font_size(self, size: int) -> None:
        self._font.setPointSize(size)
        self.setFont(self._font)
        if self._lexer is not None:
            self._lexer.setFont(self._font)
        self.setMarginsFont(self._font)
        self._resize_line_margin()

    # --- persistence -----------------------------------------------------
    def save(self, path: str | None = None) -> str:
        target = path or self.path
        if not target:
            raise ValueError("No path to save to.")
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self.text())
        self.path = target
        self.setModified(False)
        return target

    @property
    def display_name(self) -> str:
        return os.path.basename(self.path) if self.path else "untitled"
