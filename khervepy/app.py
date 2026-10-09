"""Application bootstrap for KhervePY.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import sys

# Where macOS developers keep git and Python: Homebrew (Apple Silicon, Intel),
# the python.org framework, MacPorts.
_MAC_TOOL_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/Library/Frameworks/Python.framework/Versions/Current/bin",
    "/opt/local/bin",
)


def extend_mac_path() -> None:
    """Make a Finder-launched app see the tools a Terminal session sees.

    A GUI app started from Finder or the Dock inherits launchd's minimal
    ``PATH`` (``/usr/bin:/bin:/usr/sbin:/sbin``), so Homebrew's ``git`` and any
    python.org or Homebrew Python are invisible — Run would fall back to the
    Command Line Tools stub. Append the usual directories (after the existing
    entries, so nothing the user put first is shadowed).
    """
    if sys.platform != "darwin":
        return
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    for directory in _MAC_TOOL_DIRS:
        if directory not in parts and os.path.isdir(directory):
            parts.append(directory)
    os.environ["PATH"] = os.pathsep.join(parts)


def _selftest() -> int:
    """Start the real window offscreen and check the parts a frozen build can
    lose: QScintilla, the lexers, the bundled icon. Used by the CI smoke test.

    Settings go to a throw-away folder so this never touches (or reads) the
    user's own preferences.
    """
    import tempfile

    from PyQt6.QtCore import QSettings, QTimer
    from PyQt6.QtWidgets import QApplication

    from khervepy import __app_name__, __version__

    scratch = tempfile.mkdtemp(prefix="khervepy-selftest-")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat,
                      QSettings.Scope.UserScope, scratch)

    app = QApplication(sys.argv[:1])
    app.setApplicationName(__app_name__)
    app.setOrganizationName("Gwilherm Kerherve")

    from khervepy.main_window import MainWindow
    from khervepy.resources import icon_path

    sample = os.path.join(scratch, "sample.py")
    with open(sample, "w", encoding="utf-8") as handle:
        handle.write("def hello():\n    return 'KhervePY'\n")

    window = MainWindow(initial_path=sample)
    window.show()
    app.processEvents()

    editor = window.current_editor()
    problems = []
    if editor is None:
        problems.append("no editor opened for sample.py")
    elif editor.lexer() is None:
        problems.append("no syntax lexer on a .py file (QScintilla lexers missing)")
    elif "hello" not in editor.text():
        problems.append("the file's text did not load")
    if not icon_path():
        problems.append("application icon not bundled")

    if problems:
        for line in problems:
            sys.stderr.write(f"selftest FAILED: {line}\n")
        return 1
    print(f"selftest ok: {__app_name__} {__version__}")
    QTimer.singleShot(0, app.quit)
    app.exec()
    return 0


def main() -> int:
    """Launch the KhervePY IDE. Returns the Qt exit code."""
    if "--version" in sys.argv[1:2]:
        from khervepy import __app_name__, __version__
        print(f"{__app_name__} {__version__}")
        return 0

    extend_mac_path()

    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(
            "KhervePY requires PyQt6 and QScintilla.\n"
            "Install them with:  pip install PyQt6 PyQt6-QScintilla\n"
        )
        return 1

    if "--selftest" in sys.argv[1:2]:
        return _selftest()

    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QIcon

    from khervepy import __app_name__
    from khervepy.main_window import MainWindow
    from khervepy.resources import icon_path

    class _Application(QApplication):
        """Receives ``Open With ▸ KhervePY`` and Dock drops on macOS, which
        arrive as an Apple Event (``FileOpen``), never on the command line."""

        window: MainWindow | None = None
        pending: list[str] = []

        def event(self, event):
            if event.type() == QEvent.Type.FileOpen:
                path = event.file()
                if path:
                    if self.window is None:
                        self.pending.append(path)  # Finder asked before we were up
                    else:
                        self.window.open_path(path)
                        self.window.raise_()
                        self.window.activateWindow()
                return True
            return super().event(event)

    app = _Application(sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName("Gwilherm Kerherve")
    icon = icon_path()
    if icon:
        app.setWindowIcon(QIcon(icon))

    initial = sys.argv[1] if len(sys.argv) > 1 else None
    window = MainWindow(initial_path=initial)
    window.show()
    app.window = window
    for path in app.pending:
        window.open_path(path)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
