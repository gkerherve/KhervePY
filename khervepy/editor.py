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

    # Change-bar markers (git diff vs HEAD), shown in the symbol margin.
    _MARK_ADDED = 8
    _MARK_MODIFIED = 9
    _MARK_DELETED = 10

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

        # Change-bar margin (index 1): a thin gutter of git diff markers.
        self.setMarginType(1, QsciScintilla.MarginType.SymbolMargin)
        self.setMarginWidth(1, 5)
        self.setMarginSensitivity(1, False)
        mask = (
            (1 << self._MARK_ADDED)
            | (1 << self._MARK_MODIFIED)
            | (1 << self._MARK_DELETED)
        )
        self.setMarginMarkerMask(1, mask)
        for mid, color in (
            (self._MARK_ADDED, "#3FB950"),
            (self._MARK_MODIFIED, "#58A6FF"),
            (self._MARK_DELETED, "#F85149"),
        ):
            self.markerDefine(QsciScintilla.MarkerSymbol.FullRectangle, mid)
            self.setMarkerBackgroundColor(QColor(color), mid)

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

    # --- change bar ------------------------------------------------------
    def set_change_markers(self, added, modified, deleted) -> None:
        """Repaint the gutter change-bar from 0-based line lists."""
        for mid in (self._MARK_ADDED, self._MARK_MODIFIED, self._MARK_DELETED):
            self.markerDeleteAll(mid)
        last = max(0, self.lines() - 1)
        for ln in added:
            self.markerAdd(ln, self._MARK_ADDED)
        for ln in modified:
            self.markerAdd(ln, self._MARK_MODIFIED)
        for ln in deleted:
            self.markerAdd(min(ln, last), self._MARK_DELETED)

    # --- editing commands (Code menu) ------------------------------------
    # Line- and block-comment tokens by file extension.
    _LINE_TOKENS = {
        ".py": "#", ".pyw": "#", ".sh": "#", ".rb": "#", ".yaml": "#",
        ".yml": "#", ".toml": "#", ".cfg": "#", ".conf": "#", ".r": "#",
        ".pl": "#", ".ini": ";",
        ".js": "//", ".jsx": "//", ".ts": "//", ".tsx": "//", ".c": "//",
        ".h": "//", ".cpp": "//", ".hpp": "//", ".cc": "//", ".cs": "//",
        ".java": "//", ".go": "//", ".rs": "//", ".php": "//", ".swift": "//",
        ".kt": "//", ".scala": "//",
        ".sql": "--", ".lua": "--",
    }
    _BLOCK_TOKENS = {
        ".js": ("/*", "*/"), ".jsx": ("/*", "*/"), ".ts": ("/*", "*/"),
        ".tsx": ("/*", "*/"), ".c": ("/*", "*/"), ".h": ("/*", "*/"),
        ".cpp": ("/*", "*/"), ".hpp": ("/*", "*/"), ".cc": ("/*", "*/"),
        ".cs": ("/*", "*/"), ".java": ("/*", "*/"), ".go": ("/*", "*/"),
        ".rs": ("/*", "*/"), ".php": ("/*", "*/"), ".swift": ("/*", "*/"),
        ".kt": ("/*", "*/"), ".css": ("/*", "*/"), ".scss": ("/*", "*/"),
        ".html": ("<!--", "-->"), ".xml": ("<!--", "-->"),
    }

    def _ext(self) -> str:
        return os.path.splitext(self.path or "")[1].lower()

    def toggle_line_comment(self) -> None:
        token = self._LINE_TOKENS.get(self._ext())
        if not token:
            self.toggle_block_comment()
            return
        had_selection = self.hasSelectedText()
        if had_selection:
            l1, _i1, l2, i2 = self.getSelection()
            if l2 > l1 and i2 == 0:  # selection ends at a line start
                l2 -= 1
        else:
            l1, _ = self.getCursorPosition()
            l2 = l1
        lines = range(l1, l2 + 1)
        # Comment unless every non-blank line is already commented.
        commented = all(
            not self.text(ln).strip() or self.text(ln).strip().startswith(token)
            for ln in lines
        )
        self.beginUndoAction()
        for ln in lines:
            raw = self.text(ln).rstrip("\r\n")
            if not raw.strip():
                continue
            if commented:
                idx = raw.find(token)
                if idx < 0:
                    continue
                length = len(token)
                if raw[idx + length: idx + length + 1] == " ":
                    length += 1
                self.setSelection(ln, idx, ln, idx + length)
                self.removeSelectedText()
            else:
                indent = len(raw) - len(raw.lstrip())
                self.insertAt(token + " ", ln, indent)
        self.endUndoAction()
        # Preserve the selection so repeated toggles work; else advance a line.
        if had_selection:
            self.setSelection(l1, 0, l2, len(self.text(l2).rstrip("\r\n")))
        else:
            self.setCursorPosition(min(l1 + 1, max(0, self.lines() - 1)), 0)

    def toggle_block_comment(self) -> None:
        pair = self._BLOCK_TOKENS.get(self._ext())
        if not pair:
            return
        open_t, close_t = pair
        self.beginUndoAction()
        if self.hasSelectedText():
            sel = self.selectedText()
            stripped = sel.strip()
            if stripped.startswith(open_t) and stripped.endswith(close_t):
                inner = stripped[len(open_t):-len(close_t)].strip()
                self.replaceSelectedText(inner)
            else:
                self.replaceSelectedText(f"{open_t} {sel} {close_t}")
        else:
            line, _ = self.getCursorPosition()
            raw = self.text(line).rstrip("\r\n")
            self.setSelection(line, 0, line, len(raw))
            self.replaceSelectedText(f"{open_t} {raw.strip()} {close_t}")
        self.endUndoAction()

    def duplicate_line(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_SELECTIONDUPLICATE)

    def delete_line(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_LINEDELETE)

    def move_line_up(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_MOVESELECTEDLINESUP)

    def move_line_down(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_MOVESELECTEDLINESDOWN)

    def toggle_fold(self) -> None:
        line, _ = self.getCursorPosition()
        self.foldLine(line)

    def fold_all(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_FOLDALL, 0)  # SC_FOLDACTION_CONTRACT

    def unfold_all(self) -> None:
        self.SendScintilla(QsciScintilla.SCI_FOLDALL, 1)  # SC_FOLDACTION_EXPAND

    def reload_from_disk(self) -> None:
        """Reload the buffer from ``self.path`` (e.g. after an external edit)."""
        if not self.path or not os.path.isfile(self.path):
            return
        line, index = self.getCursorPosition()
        self._load(self.path)
        self.setCursorPosition(min(line, max(0, self.lines() - 1)), index)

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
