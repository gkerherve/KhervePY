"""Map file extensions to QScintilla lexers.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os


def make_lexer(path: str):
    """Return a fresh QScintilla lexer for ``path`` or ``None`` for plain text.

    Imported lazily so the module stays importable without Qt bindings.
    """
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

    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path).lower()

    by_ext = {
        ".py": QsciLexerPython,
        ".pyw": QsciLexerPython,
        ".pyi": QsciLexerPython,
        ".js": QsciLexerJavaScript,
        ".jsx": QsciLexerJavaScript,
        ".mjs": QsciLexerJavaScript,
        ".ts": QsciLexerJavaScript,
        ".tsx": QsciLexerJavaScript,
        ".c": QsciLexerCPP,
        ".h": QsciLexerCPP,
        ".cpp": QsciLexerCPP,
        ".cc": QsciLexerCPP,
        ".hpp": QsciLexerCPP,
        ".cs": QsciLexerCPP,
        ".java": QsciLexerCPP,
        ".go": QsciLexerCPP,
        ".rs": QsciLexerCPP,
        ".html": QsciLexerHTML,
        ".htm": QsciLexerHTML,
        ".css": QsciLexerCSS,
        ".scss": QsciLexerCSS,
        ".json": QsciLexerJSON,
        ".md": QsciLexerMarkdown,
        ".markdown": QsciLexerMarkdown,
        ".sh": QsciLexerBash,
        ".bash": QsciLexerBash,
        ".zsh": QsciLexerBash,
        ".yml": QsciLexerYAML,
        ".yaml": QsciLexerYAML,
        ".sql": QsciLexerSQL,
        ".xml": QsciLexerXML,
    }

    by_name = {
        "dockerfile": QsciLexerBash,
        "makefile": QsciLexerBash,
        ".gitignore": QsciLexerBash,
        "requirements.txt": QsciLexerBash,
    }

    cls = by_ext.get(ext) or by_name.get(name)
    return cls() if cls else None
