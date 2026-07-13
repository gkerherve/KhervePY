"""Application bootstrap for KhervePY.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Launch the KhervePY IDE. Returns the Qt exit code."""
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(
            "KhervePY requires PyQt6 and QScintilla.\n"
            "Install them with:  pip install PyQt6 PyQt6-QScintilla\n"
        )
        return 1

    from PyQt6.QtGui import QIcon

    from khervepy import __app_name__
    from khervepy.main_window import MainWindow
    from khervepy.resources import icon_path

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName("Gwilherm Kerherve")
    icon = icon_path()
    if icon:
        app.setWindowIcon(QIcon(icon))

    initial = sys.argv[1] if len(sys.argv) > 1 else None
    window = MainWindow(initial_path=initial)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
