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
    "Nord": Theme(
        name="Nord",
        background="#2E3440",
        foreground="#D8DEE9",
        caret="#D8DEE9",
        caret_line="#3B4252",
        selection_bg="#434C5E",
        selection_fg="#ECEFF4",
        margin_bg="#2E3440",
        margin_fg="#4C566A",
        fold_bg="#3B4252",
        indicator="#88C0D0",
        roles={
            "keyword": "#81A1C1",
            "comment": "#616E88",
            "string": "#A3BE8C",
            "number": "#B48EAD",
            "operator": "#81A1C1",
            "class": "#8FBCBB",
            "function": "#88C0D0",
            "decorator": "#D08770",
            "preprocessor": "#5E81AC",
            "identifier": "#D8DEE9",
            "default": "#D8DEE9",
        },
    ),
    "Gruvbox Dark": Theme(
        name="Gruvbox Dark",
        background="#282828",
        foreground="#EBDBB2",
        caret="#EBDBB2",
        caret_line="#3C3836",
        selection_bg="#504945",
        selection_fg="#FBF1C7",
        margin_bg="#282828",
        margin_fg="#7C6F64",
        fold_bg="#3C3836",
        indicator="#83A598",
        roles={
            "keyword": "#FB4934",
            "comment": "#928374",
            "string": "#B8BB26",
            "number": "#D3869B",
            "operator": "#FE8019",
            "class": "#FABD2F",
            "function": "#B8BB26",
            "decorator": "#8EC07C",
            "preprocessor": "#FE8019",
            "identifier": "#EBDBB2",
            "default": "#EBDBB2",
        },
    ),
    "Tokyo Night": Theme(
        name="Tokyo Night",
        background="#1A1B26",
        foreground="#A9B1D6",
        caret="#C0CAF5",
        caret_line="#24283B",
        selection_bg="#33467C",
        selection_fg="#C0CAF5",
        margin_bg="#1A1B26",
        margin_fg="#565F89",
        fold_bg="#24283B",
        indicator="#7AA2F7",
        roles={
            "keyword": "#BB9AF7",
            "comment": "#565F89",
            "string": "#9ECE6A",
            "number": "#FF9E64",
            "operator": "#89DDFF",
            "class": "#2AC3DE",
            "function": "#7AA2F7",
            "decorator": "#E0AF68",
            "preprocessor": "#7DCFFF",
            "identifier": "#A9B1D6",
            "default": "#A9B1D6",
        },
    ),
    "GitHub Dark": Theme(
        name="GitHub Dark",
        background="#0D1117",
        foreground="#C9D1D9",
        caret="#58A6FF",
        caret_line="#161B22",
        selection_bg="#264F78",
        selection_fg="#C9D1D9",
        margin_bg="#0D1117",
        margin_fg="#484F58",
        fold_bg="#161B22",
        indicator="#58A6FF",
        roles={
            "keyword": "#FF7B72",
            "comment": "#8B949E",
            "string": "#A5D6FF",
            "number": "#79C0FF",
            "operator": "#FF7B72",
            "class": "#FFA657",
            "function": "#D2A8FF",
            "decorator": "#7EE787",
            "preprocessor": "#7EE787",
            "identifier": "#C9D1D9",
            "default": "#C9D1D9",
        },
    ),
    "Material Ocean": Theme(
        name="Material Ocean",
        background="#0F111A",
        foreground="#A6ACCD",
        caret="#FFCC00",
        caret_line="#1F2233",
        selection_bg="#1F2233",
        selection_fg="#FFFFFF",
        margin_bg="#0F111A",
        margin_fg="#464B5D",
        fold_bg="#1F2233",
        indicator="#82AAFF",
        roles={
            "keyword": "#C792EA",
            "comment": "#464B5D",
            "string": "#C3E88D",
            "number": "#F78C6C",
            "operator": "#89DDFF",
            "class": "#FFCB6B",
            "function": "#82AAFF",
            "decorator": "#F07178",
            "preprocessor": "#82AAFF",
            "identifier": "#A6ACCD",
            "default": "#A6ACCD",
        },
    ),
    "Cobalt2": Theme(
        name="Cobalt2",
        background="#193549",
        foreground="#FFFFFF",
        caret="#FFC600",
        caret_line="#1F4662",
        selection_bg="#0050A4",
        selection_fg="#FFFFFF",
        margin_bg="#15232D",
        margin_fg="#4F6675",
        fold_bg="#15232D",
        indicator="#FFC600",
        roles={
            "keyword": "#FF9D00",
            "comment": "#638194",
            "string": "#3AD900",
            "number": "#FF628C",
            "operator": "#FFFFFF",
            "class": "#FFDD00",
            "function": "#FFC600",
            "decorator": "#FF9D00",
            "preprocessor": "#FF9D00",
            "identifier": "#FFFFFF",
            "default": "#FFFFFF",
        },
    ),
}

DEFAULT_THEME = "Darcula"


def theme_names():
    """Return the catalogue keys in a stable, presentation-friendly order."""
    return list(THEMES.keys())


def window_stylesheet(t: Theme) -> str:
    """Return a Qt stylesheet that dresses the whole window in ``t``'s colours."""
    return f"""
QWidget {{ background: {t.background}; color: {t.foreground}; }}
QMainWindow::separator {{ background: {t.margin_fg}; width: 1px; height: 1px; }}
QToolBar {{ background: {t.fold_bg}; border: 0px; border-bottom: 1px solid {t.margin_fg};
           padding: 3px; spacing: 3px; }}
QToolButton {{ background: transparent; padding: 4px; border-radius: 4px; color: {t.foreground}; }}
QToolButton:hover {{ background: {t.selection_bg}; }}
QToolButton:pressed {{ background: {t.selection_bg}; }}
QMenuBar {{ background: {t.background}; color: {t.foreground}; }}
QMenuBar::item {{ background: transparent; padding: 4px 9px; }}
QMenuBar::item:selected {{ background: {t.selection_bg}; }}
QMenu {{ background: {t.margin_bg}; color: {t.foreground}; border: 1px solid {t.margin_fg}; }}
QMenu::item {{ padding: 4px 22px; }}
QMenu::item:selected {{ background: {t.selection_bg}; color: {t.selection_fg}; }}
QMenu::separator {{ height: 1px; background: {t.margin_fg}; margin: 4px 8px; }}
QDockWidget {{ color: {t.foreground}; }}
QDockWidget::title {{ background: {t.fold_bg}; padding: 5px 8px; }}
QTabWidget::pane {{ border: 1px solid {t.margin_fg}; }}
QTabBar::tab {{ background: {t.fold_bg}; color: {t.margin_fg}; padding: 5px 12px; border: 0px; }}
QTabBar::tab:selected {{ background: {t.background}; color: {t.foreground}; }}
QTabBar::tab:hover {{ color: {t.foreground}; }}
QTreeView, QTreeWidget, QListView, QListWidget {{
    background: {t.background}; color: {t.foreground}; border: 0px; outline: 0;
    alternate-background-color: {t.caret_line};
    selection-background-color: {t.selection_bg}; selection-color: {t.selection_fg}; }}
QTreeView::item:hover, QListWidget::item:hover {{ background: {t.caret_line}; }}
QHeaderView::section {{ background: {t.fold_bg}; color: {t.foreground}; border: 0px;
    border-right: 1px solid {t.margin_fg}; padding: 4px 6px; }}
QLineEdit, QPlainTextEdit, QTextEdit {{ background: {t.caret_line}; color: {t.foreground};
    border: 1px solid {t.margin_fg}; border-radius: 3px; padding: 3px;
    selection-background-color: {t.selection_bg}; selection-color: {t.selection_fg}; }}
QComboBox {{ background: {t.caret_line}; color: {t.foreground};
    border: 1px solid {t.margin_fg}; border-radius: 3px; padding: 2px 6px; }}
QComboBox QAbstractItemView {{ background: {t.margin_bg}; color: {t.foreground};
    selection-background-color: {t.selection_bg}; }}
QPushButton {{ background: {t.fold_bg}; color: {t.foreground}; border: 1px solid {t.margin_fg};
    border-radius: 4px; padding: 4px 10px; }}
QPushButton:hover {{ background: {t.selection_bg}; }}
QPushButton:disabled {{ color: {t.margin_fg}; border-color: {t.margin_fg}; }}
QCheckBox {{ background: transparent; color: {t.foreground}; }}
QLabel {{ background: transparent; color: {t.foreground}; }}
QStatusBar {{ background: {t.fold_bg}; color: {t.foreground}; }}
QStatusBar QPushButton {{ background: transparent; border: 0px; padding: 2px 6px; }}
QScrollBar:vertical {{ background: {t.background}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t.margin_fg}; min-height: 24px;
    border-radius: 5px; margin: 2px; }}
QScrollBar:horizontal {{ background: {t.background}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t.margin_fg}; min-width: 24px;
    border-radius: 5px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QSplitter::handle {{ background: {t.margin_fg}; }}
"""


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
