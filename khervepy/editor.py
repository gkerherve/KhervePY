"""The code-editor widget: a configured ``QsciScintilla`` instance.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import codecs
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics
from PyQt6.Qsci import QsciScintilla

from khervepy.fonts import mono_font
from khervepy.lexers import make_lexer
from khervepy.themes import THEMES, DEFAULT_THEME, apply_theme


# Above this a file opens as plain text (no lexer, folding or change bar) and
# above the hard limit it is not opened at all: Scintilla is fast, but lexing
# and diffing a 30 MB log on every keystroke is not.
PLAIN_ABOVE = 2 * 1024 * 1024
REFUSE_ABOVE = 40 * 1024 * 1024

# What the status-bar encoding menu offers: (label, codec).
ENCODINGS = [
    ("UTF-8", "utf-8"),
    ("UTF-8 with BOM", "utf-8-sig"),
    ("UTF-16", "utf-16"),
    ("Windows-1252", "cp1252"),
    ("Latin-1 (ISO-8859-1)", "latin-1"),
]
EOLS = [("LF  (Unix, macOS)", "\n"), ("CRLF  (Windows)", "\r\n"), ("CR  (classic Mac)", "\r")]


def decode_bytes(raw: bytes) -> tuple[str, str]:
    """Decode *raw* without ever losing a byte; return ``(text, codec)``.

    A BOM decides first (UTF-8-SIG, UTF-16). Then strict UTF-8. Anything else
    is treated as Windows-1252 (the usual culprit), falling back to Latin-1,
    which decodes every byte — so saving writes the same bytes back instead of
    the lossy ``errors="replace"`` the editor used to apply.
    """
    if raw.startswith(codecs.BOM_UTF8):
        return raw[3:].decode("utf-8"), "utf-8-sig"
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16"), "utf-16"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1"


def detect_eol(text: str) -> str:
    """The line ending most lines use ("\n" when there are none)."""
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    best = max((lf, "\n"), (crlf, "\r\n"), (cr, "\r"))
    return best[1] if best[0] else "\n"


class FileTooLarge(Exception):
    """Raised by the loader when a file is beyond ``REFUSE_ABOVE``."""


class BinaryFile(Exception):
    """Raised by the loader for a file that is not text (NUL bytes, no UTF-16 BOM)."""


class CodeEditor(QsciScintilla):
    """A single editable buffer, theme-aware and language-aware."""

    # Change-bar markers (git diff vs HEAD), shown in the symbol margin.
    _MARK_ADDED = 8
    _MARK_MODIFIED = 9
    _MARK_DELETED = 10

    def __init__(self, path: str | None = None, font_size: int = 11, parent=None):
        super().__init__(parent)
        self.path = path
        self.encoding = "utf-8"        # codec the file is read and written with
        self.eol = "\n"                # line ending written on save
        self.plain = False             # opened as plain text (very large file)
        self._disk_sig: tuple | None = None   # (mtime_ns, size) at last load/save
        self._missing_reported = False
        self._lexer = None
        self._font = mono_font(font_size)

        self._configure_editor()
        if path and os.path.isfile(path):
            self._load(path)
        self.set_lexer_for_path(path or "")
        self.apply_theme(DEFAULT_THEME)
        if self.plain:
            self.setFolding(QsciScintilla.FoldStyle.NoFoldStyle)
            self.setIndentationGuides(False)

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

        # Multiple carets: Cmd/Ctrl-click adds one, Alt-drag makes a column
        # selection, and typing / pasting applies to every caret.
        self.SendScintilla(QsciScintilla.SCI_SETMULTIPLESELECTION, 1)
        self.SendScintilla(QsciScintilla.SCI_SETADDITIONALSELECTIONTYPING, 1)
        self.SendScintilla(QsciScintilla.SCI_SETMULTIPASTE, 1)
        self.SendScintilla(QsciScintilla.SCI_SETADDITIONALCARETSVISIBLE, 1)

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
            size = os.path.getsize(path)
            if size > REFUSE_ABOVE:
                raise FileTooLarge(path)
            with open(path, "rb") as fh:
                raw = fh.read()
        except FileTooLarge:
            raise
        except OSError:
            self.setText("")
            self.setModified(False)
            return
        if b"\x00" in raw[:8192] and not raw.startswith(
                (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            raise BinaryFile(path)
        text, self.encoding = decode_bytes(raw)
        self.eol = detect_eol(text)
        self.plain = len(raw) > PLAIN_ABOVE
        # The buffer always holds "\n"; the file's own ending is put back on
        # save, so a CRLF file stays CRLF instead of being rewritten as LF.
        self.setText(text.replace("\r\n", "\n").replace("\r", "\n"))
        self.setModified(False)
        self._resize_line_margin()
        self.mark_disk_synced()

    # --- disk state (external edits) ---------------------------------------
    def _stat_sig(self) -> tuple | None:
        try:
            st = os.stat(self.path)
        except (OSError, TypeError):
            return None
        return (st.st_mtime_ns, st.st_size)

    def mark_disk_synced(self) -> None:
        """Remember the file as it is on disk right now (after load or save)."""
        self._disk_sig = self._stat_sig()
        self._missing_reported = False

    def disk_state(self) -> str:
        """``"same"``, ``"changed"`` or ``"missing"`` versus our last sync."""
        if not self.path or self._disk_sig is None:
            return "same"
        sig = self._stat_sig()
        if sig is None:
            return "missing"
        return "same" if sig == self._disk_sig else "changed"

    def set_encoding(self, codec: str) -> None:
        """Change the codec the next save uses; marks the buffer modified."""
        if codec != self.encoding:
            self.encoding = codec
            self.setModified(True)

    def set_eol(self, eol: str) -> None:
        if eol != self.eol:
            self.eol = eol
            self.setModified(True)

    @property
    def eol_name(self) -> str:
        return {"\n": "LF", "\r\n": "CRLF", "\r": "CR"}.get(self.eol, "LF")

    @property
    def encoding_name(self) -> str:
        for label, codec in ENCODINGS:
            if codec == self.encoding:
                return label.split(" (")[0]
        return self.encoding.upper()

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
        top = self.SendScintilla(QsciScintilla.SCI_GETFIRSTVISIBLELINE)
        self._load(self.path)
        self.setCursorPosition(min(line, max(0, self.lines() - 1)), index)
        self.SendScintilla(QsciScintilla.SCI_SETFIRSTVISIBLELINE, top)

    # --- persistence -----------------------------------------------------
    def save(self, path: str | None = None) -> str:
        target = path or self.path
        if not target:
            raise ValueError("No path to save to.")
        text = self.text().replace("\r\n", "\n").replace("\r", "\n")
        if self.eol != "\n":
            text = text.replace("\n", self.eol)
        try:
            data = text.encode(self.encoding)
        except UnicodeEncodeError:
            # e.g. an emoji typed into a Windows-1252 file: widen rather than
            # silently mangling it or refusing to save.
            self.encoding = "utf-8"
            data = text.encode("utf-8")
        if self.encoding == "utf-16":          # Python's own writes a BOM
            data = codecs.BOM_UTF16_LE + text.encode("utf-16-le")
        with open(target, "wb") as fh:
            fh.write(data)
        self.path = target
        self.setModified(False)
        self.mark_disk_synced()
        return target

    # --- multiple carets ---------------------------------------------------
    def _selection_ranges(self) -> list[tuple[int, int]]:
        sci = QsciScintilla
        return [(self.SendScintilla(sci.SCI_GETSELECTIONNSTART, i),
                 self.SendScintilla(sci.SCI_GETSELECTIONNEND, i))
                for i in range(self.SendScintilla(sci.SCI_GETSELECTIONS))]

    def add_next_occurrence(self) -> bool:
        """Select the word under the caret; each further call adds the next match.

        Wraps around the end of the document and skips matches already
        selected. (Scintilla's own SCI_MULTIPLESELECTADDNEXT only ever selected
        the word in this build, so the search is done here.) Returns False when
        there is nothing new to add.
        """
        sci = QsciScintilla
        if self.SendScintilla(sci.SCI_GETSELECTIONEMPTY):
            pos = self.SendScintilla(sci.SCI_GETCURRENTPOS)
            start = self.SendScintilla(sci.SCI_WORDSTARTPOSITION, pos, True)
            end = self.SendScintilla(sci.SCI_WORDENDPOSITION, pos, True)
            if end > start:
                self.SendScintilla(sci.SCI_SETSELECTION, end, start)
                return True
            return False
        # (selectedText() lags behind until the event loop runs; ask Scintilla.)
        main = self.SendScintilla(sci.SCI_GETMAINSELECTION)
        lo = self.SendScintilla(sci.SCI_GETSELECTIONNSTART, main)
        hi = self.SendScintilla(sci.SCI_GETSELECTIONNEND, main)
        needle = self.text(lo, hi).encode("utf-8")
        if not needle:
            return False
        taken = set(self._selection_ranges())
        doc_len = self.SendScintilla(sci.SCI_GETLENGTH)
        last_end = max(end for _start, end in taken)
        self.SendScintilla(sci.SCI_SETSEARCHFLAGS, sci.SCFIND_MATCHCASE)
        for lo, hi in ((last_end, doc_len), (0, last_end)):
            self.SendScintilla(sci.SCI_SETTARGETSTART, lo)
            self.SendScintilla(sci.SCI_SETTARGETEND, hi)
            pos = self.SendScintilla(sci.SCI_SEARCHINTARGET, len(needle), needle)
            while pos >= 0:
                if (pos, pos + len(needle)) not in taken:
                    self.SendScintilla(sci.SCI_ADDSELECTION, pos + len(needle), pos)
                    return True
                self.SendScintilla(sci.SCI_SETTARGETSTART, pos + len(needle))
                self.SendScintilla(sci.SCI_SETTARGETEND, hi)
                pos = self.SendScintilla(sci.SCI_SEARCHINTARGET, len(needle), needle)
        return False

    def select_all_occurrences(self) -> None:
        """Select every occurrence of the word / selection at once."""
        if self.SendScintilla(QsciScintilla.SCI_GETSELECTIONEMPTY) and not self.add_next_occurrence():
            return
        for _ in range(10000):                      # a safety cap, not a real limit
            if not self.add_next_occurrence():
                break

    @property
    def display_name(self) -> str:
        return os.path.basename(self.path) if self.path else "untitled"
