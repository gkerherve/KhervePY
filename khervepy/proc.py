"""Process helpers shared across KhervePY.

Two concerns handled here, both mattering mainly for the *frozen* (PyInstaller)
build on Windows:

* **No flashing consoles.** A windowed app has no console, so every child
  console program (``git``, ``cmd``, ``python``) would otherwise pop its own
  console window. ``CREATE_NO_WINDOW`` suppresses that for both
  ``subprocess`` and ``QProcess`` children.
* **A real Python interpreter.** In a frozen build ``sys.executable`` is
  ``KhervePY.exe`` itself, not Python — so Run/Debug/pip must locate an actual
  interpreter instead.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

_IS_WINDOWS = os.name == "nt"
_CREATE_NO_WINDOW = 0x08000000  # Windows process-creation flag


def subprocess_flags() -> dict:
    """Keyword args for ``subprocess.run`` that suppress a console window."""
    if not _IS_WINDOWS:
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"creationflags": _CREATE_NO_WINDOW, "startupinfo": startupinfo}


def hide_console(proc) -> None:
    """Stop a ``QProcess`` child from opening a console window (Windows)."""
    if not _IS_WINDOWS:
        return
    try:
        def _modifier(args):
            args.flags |= _CREATE_NO_WINDOW
        proc.setCreateProcessArgumentsModifier(_modifier)
    except (AttributeError, TypeError):
        # Older/other Qt builds without the modifier hook: nothing to do.
        pass


def python_executable(project_root: str | None = None) -> str:
    """Return a usable Python interpreter path.

    When running from source this is simply ``sys.executable``. In a frozen
    build ``sys.executable`` is the app itself, so prefer the project's own
    virtualenv, then any ``python`` on ``PATH``. Returns "" if none is found.
    """
    if not getattr(sys, "frozen", False):
        return sys.executable

    if project_root:
        sub = "Scripts" if _IS_WINDOWS else "bin"
        exe = "python.exe" if _IS_WINDOWS else "python"
        for name in ("venv", ".venv", "env", ".env"):
            candidate = os.path.join(project_root, name, sub, exe)
            if os.path.isfile(candidate):
                return candidate

    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found:
            return found
    return ""
