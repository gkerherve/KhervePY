"""Syntax-highlighting themes for KhervePY.

Each theme describes editor "chrome" (background, caret, selection, margins)
plus a set of semantic *roles* (keyword, comment, string, ...). Roles are
mapped onto the concrete style numbers of each QScintilla lexer by
``apply_theme`` so a single theme colours every supported language.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

try:  # Qt is optional at import time so the module can be introspected headless.
    from PyQt6.QtGui import QColor, QFont
    from PyQt6.Qsci import (
        QsciLexerPython,
        QsciLexerJavaScript,
        QsciLexerCPP,
        QsciLexerHTML,
        QsciLexerCSS,
        QsciLexerJSON,
        QsciLexerMarkdown,
        QsciLexerBash,
        QsciLexerYAML,
        QsciLexerSQL,
        QsciLexerXML,
    )
    _QT = True
except Exception:  # pragma: no cover - headless / missing bindings
    _QT = False


# --- Semantic roles ---------------------------------------------------------
# These are the language-agnostic token classes a theme colours.
ROLES = (
    "default",
    "keyword",
    "comment",
    "string",
    "number",
    "operator",
    "class",
    "function",
    "decorator",
    "preprocessor",
    "identifier",
)


@dataclass
class Theme:
    """A named colour scheme."""

    name: str
    background: str
    foreground: str
    caret: str
    caret_line: str
    selection_bg: str
    selection_fg: str
    margin_bg: str
    margin_fg: str
    fold_bg: str
    indicator: str
    roles: Dict[str, str] = field(default_factory=dict)

    def role(self, name: str) -> str:
        return self.roles.get(name, self.foreground)


# --- Theme catalogue --------------------------------------------------------
THEMES: Dict[str, Theme] = {
    "Darcula": Theme(
        name="Darcula",
        background="#2B2B2B",
        foreground="#A9B7C6",
        caret="#BBBBBB",
        caret_line="#323232",
        selection_bg="#214283",
        selection_fg="#A9B7C6",
        margin_bg="#313335",
        margin_fg="#606366",
        fold_bg="#313335",
        indicator="#3592C4",
        roles={
            "keyword": "#CC7832",
            "comment": "#808080",
            "string": "#6A8759",
            "number": "#6897BB",
            "operator": "#A9B7C6",
            "class": "#A9B7C6",
            "function": "#FFC66D",
            "decorator": "#BBB529",
            "preprocessor": "#BBB529",
            "identifier": "#A9B7C6",
            "default": "#A9B7C6",
        },
    ),
    "One Dark": Theme(
        name="One Dark",
        background="#282C34",
        foreground="#ABB2BF",
        caret="#528BFF",
        caret_line="#2C313C",
        selection_bg="#3E4451",
        selection_fg="#ABB2BF",
        margin_bg="#282C34",
        margin_fg="#4B5263",
        fold_bg="#21252B",
        indicator="#61AFEF",
        roles={
            "keyword": "#C678DD",
            "comment": "#5C6370",
            "string": "#98C379",
            "number": "#D19A66",
            "operator": "#56B6C2",
            "class": "#E5C07B",
            "function": "#61AFEF",
            "decorator": "#E06C75",
            "preprocessor": "#E06C75",
            "identifier": "#ABB2BF",
            "default": "#ABB2BF",
        },
    ),
    "Monokai": Theme(
        name="Monokai",
        background="#272822",
        foreground="#F8F8F2",
        caret="#F8F8F0",
        caret_line="#3E3D32",
        selection_bg="#49483E",
        selection_fg="#F8F8F2",
        margin_bg="#272822",
        margin_fg="#75715E",
        fold_bg="#1E1F1C",
        indicator="#66D9EF",
        roles={
            "keyword": "#F92672",
            "comment": "#75715E",
            "string": "#E6DB74",
            "number": "#AE81FF",
            "operator": "#F92672",
            "class": "#A6E22E",
            "function": "#A6E22E",
            "decorator": "#66D9EF",
            "preprocessor": "#66D9EF",
            "identifier": "#F8F8F2",
            "default": "#F8F8F2",
        },
    ),
    "Solarized Dark": Theme(
        name="Solarized Dark",
        background="#002B36",
        foreground="#839496",
        caret="#93A1A1",
        caret_line="#073642",
        selection_bg="#073642",
        selection_fg="#93A1A1",
        margin_bg="#073642",
        margin_fg="#586E75",
        fold_bg="#073642",
        indicator="#268BD2",
        roles={
            "keyword": "#859900",
            "comment": "#586E75",
            "string": "#2AA198",
            "number": "#D33682",
            "operator": "#839496",
            "class": "#B58900",
            "function": "#268BD2",
            "decorator": "#CB4B16",
            "preprocessor": "#CB4B16",
            "identifier": "#839496",
            "default": "#839496",
        },
    ),
    "Dracula": Theme(
        name="Dracula",
        background="#282A36",
        foreground="#F8F8F2",
        caret="#F8F8F0",
        caret_line="#343746",
        selection_bg="#44475A",
        selection_fg="#F8F8F2",
        margin_bg="#282A36",
        margin_fg="#6272A4",
        fold_bg="#21222C",
        indicator="#BD93F9",
        roles={
            "keyword": "#FF79C6",
            "comment": "#6272A4",
            "string": "#F1FA8C",
            "number": "#BD93F9",
            "operator": "#FF79C6",
            "class": "#8BE9FD",
            "function": "#50FA7B",
            "decorator": "#8BE9FD",
            "preprocessor": "#8BE9FD",
            "identifier": "#F8F8F2",
            "default": "#F8F8F2",
        },
    ),
    "GitHub Light": Theme(
        name="GitHub Light",
        background="#FFFFFF",
        foreground="#24292E",
        caret="#044289",
        caret_line="#F6F8FA",
        selection_bg="#C8E1FF",
        selection_fg="#24292E",
        margin_bg="#FFFFFF",
        margin_fg="#BABBBD",
        fold_bg="#F6F8FA",
        indicator="#0366D6",
        roles={
            "keyword": "#D73A49",
            "comment": "#6A737D",
            "string": "#032F62",
            "number": "#005CC5",
            "operator": "#D73A49",
            "class": "#6F42C1",
            "function": "#6F42C1",
            "decorator": "#22863A",
            "preprocessor": "#22863A",
            "identifier": "#24292E",
            "default": "#24292E",
        },
    ),
    "Solarized Light": Theme(
        name="Solarized Light",
        background="#FDF6E3",
        foreground="#657B83",
        caret="#586E75",
        caret_line="#EEE8D5",
        selection_bg="#EEE8D5",
        selection_fg="#586E75",
        margin_bg="#EEE8D5",
        margin_fg="#93A1A1",
        fold_bg="#EEE8D5",
        indicator="#268BD2",
        roles={
            "keyword": "#859900",
            "comment": "#93A1A1",
            "string": "#2AA198",
            "number": "#D33682",
            "operator": "#657B83",
            "class": "#B58900",
            "function": "#268BD2",
            "decorator": "#CB4B16",
            "preprocessor": "#CB4B16",
            "identifier": "#657B83",
            "default": "#657B83",
        },
    ),
}

DEFAULT_THEME = "Darcula"


def theme_names():
    """Return the catalogue keys in a stable, presentation-friendly order."""
    return list(THEMES.keys())


# --- Per-lexer role -> style-number mapping ---------------------------------
# Each QScintilla lexer numbers its styles differently; this maps our semantic
# roles onto the concrete constants of the lexers we ship.
def _role_map_for(lexer):  # pragma: no cover - requires Qt
    """Return ``{style_number: role_name}`` for the given lexer instance."""
    if isinstance(lexer, QsciLexerPython):
        L = QsciLexerPython
        return {
            L.Default: "default",
            L.Keyword: "keyword",
            L.Comment: "comment",
            L.CommentBlock: "comment",
            L.SingleQuotedString: "string",
            L.DoubleQuotedString: "string",
            L.TripleSingleQuotedString: "string",
            L.TripleDoubleQuotedString: "string",
            L.SingleQuotedFString: "string",
            L.DoubleQuotedFString: "string",
            L.Number: "number",
            L.Operator: "operator",
            L.ClassName: "class",
            L.FunctionMethodName: "function",
            L.Decorator: "decorator",
            L.Identifier: "identifier",
            L.HighlightedIdentifier: "identifier",
        }
    if isinstance(lexer, (QsciLexerJavaScript, QsciLexerCPP)):
        L = type(lexer)
        return {
            L.Default: "default",
            L.Keyword: "keyword",
            L.Comment: "comment",
            L.CommentLine: "comment",
            L.CommentDoc: "comment",
            L.SingleQuotedString: "string",
            L.DoubleQuotedString: "string",
            L.RawString: "string",
            L.Number: "number",
            L.Operator: "operator",
            L.GlobalClass: "class",
            L.Identifier: "identifier",
            L.PreProcessor: "preprocessor",
        }
    if isinstance(lexer, QsciLexerJSON):
        L = QsciLexerJSON
        return {
            L.Default: "default",
            L.Keyword: "keyword",
            L.Number: "number",
            L.String: "string",
            L.Property: "class",
            L.Operator: "operator",
            L.CommentLine: "comment",
            L.CommentBlock: "comment",
        }
    if isinstance(lexer, QsciLexerMarkdown):
        L = QsciLexerMarkdown
        return {
            L.Default: "default",
            L.Header1: "keyword",
            L.Header2: "keyword",
            L.Header3: "keyword",
            L.CodeBackticks: "string",
            L.CodeBlock: "string",
            L.Link: "function",
        }
    if isinstance(lexer, QsciLexerBash):
        L = QsciLexerBash
        return {
            L.Default: "default",
            L.Keyword: "keyword",
            L.Comment: "comment",
            L.SingleQuotedString: "string",
            L.DoubleQuotedString: "string",
            L.Number: "number",
            L.Operator: "operator",
            L.Identifier: "identifier",
        }
    if isinstance(lexer, QsciLexerYAML):
        L = QsciLexerYAML
        return {
            L.Default: "default",
            L.Keyword: "keyword",
            L.Comment: "comment",
            L.Number: "number",
            L.Identifier: "class",
            L.Operator: "operator",
        }
    if isinstance(lexer, QsciLexerSQL):
        L = QsciLexerSQL
        return {
            L.Default: "default",
            L.Keyword: "keyword",
            L.Comment: "comment",
            L.CommentLine: "comment",
            L.SingleQuotedString: "string",
            L.DoubleQuotedString: "string",
            L.Number: "number",
            L.Operator: "operator",
            L.Identifier: "identifier",
        }
    if isinstance(lexer, (QsciLexerHTML, QsciLexerXML)):
        L = type(lexer)
        return {
            L.Default: "default",
            L.Tag: "keyword",
            L.Attribute: "function",
            L.HTMLComment: "comment",
            L.HTMLDoubleQuotedString: "string",
            L.HTMLSingleQuotedString: "string",
            L.HTMLNumber: "number",
        }
    if isinstance(lexer, QsciLexerCSS):
        L = QsciLexerCSS
        return {
            L.Default: "default",
            L.Tag: "keyword",
            L.ClassSelector: "class",
            L.IDSelector: "function",
            L.Comment: "comment",
            L.DoubleQuotedString: "string",
            L.SingleQuotedString: "string",
            L.CSS1Property: "keyword",
            L.Value: "number",
        }
    return {}


def apply_theme(editor, lexer, theme: Theme):  # pragma: no cover - requires Qt
    """Paint ``editor`` and ``lexer`` with ``theme``.

    Works with or without a lexer; when a lexer is present its per-token styles
    are coloured from the theme's semantic roles.
    """
    if not _QT:
        return

    bg = QColor(theme.background)
    fg = QColor(theme.foreground)

    # Editor chrome -------------------------------------------------------
    editor.setCaretForegroundColor(QColor(theme.caret))
    editor.setCaretLineBackgroundColor(QColor(theme.caret_line))
    editor.setSelectionBackgroundColor(QColor(theme.selection_bg))
    editor.setSelectionForegroundColor(QColor(theme.selection_fg))
    editor.setMarginsBackgroundColor(QColor(theme.margin_bg))
    editor.setMarginsForegroundColor(QColor(theme.margin_fg))
    editor.setFoldMarginColors(QColor(theme.fold_bg), QColor(theme.fold_bg))
    editor.setPaper(bg)
    editor.setColor(fg)

    if lexer is None:
        # Plain-text buffer: paint the default style directly.
        editor.setPaper(bg)
        editor.setColor(fg)
        return

    # Base: paint every style slot so unmapped tokens still match the theme.
    lexer.setDefaultPaper(bg)
    lexer.setDefaultColor(fg)
    for style in range(128):
        lexer.setPaper(bg, style)
        lexer.setColor(fg, style)

    for style, role in _role_map_for(lexer).items():
        lexer.setColor(QColor(theme.role(role)), style)
        lexer.setPaper(bg, style)
