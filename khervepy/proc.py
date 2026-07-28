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
    """Keyword args for ``subprocess.run`` used across KhervePY.

    Two concerns, both bundled so every call gets them:

    * **UTF-8 decoding.** ``text=True`` alone decodes child output with the
      locale codec (cp1252 on Windows), which crashes on bytes like ``0x81`` in
      git/pip output. Force UTF-8 with ``errors="replace"`` instead.
    * **No console window.** On Windows, ``CREATE_NO_WINDOW`` stops child
      console programs from flashing a window in the frozen (windowed) build.
    """
    flags: dict = {"encoding": "utf-8", "errors": "replace"}
    if _IS_WINDOWS:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        flags["creationflags"] = _CREATE_NO_WINDOW
        flags["startupinfo"] = startupinfo
    return flags


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


def project_venv_python(project_root: str | None) -> str:
    """Return the interpreter of *project_root*'s own virtualenv, or "".

    Looks for the usual venv directory names in the project root and returns
    the interpreter inside the first one found.
    """
    if not project_root:
        return ""
    sub = "Scripts" if _IS_WINDOWS else "bin"
    exe = "python.exe" if _IS_WINDOWS else "python"
    for name in ("venv", ".venv", "env", ".env"):
        candidate = os.path.join(project_root, name, sub, exe)
        if os.path.isfile(candidate):
            return candidate
    return ""


def _base_python() -> str:
    """Return the interpreter KhervePY's own virtualenv was created from."""
    base = getattr(sys, "_base_executable", "") or ""
    if base and os.path.isfile(base):
        return base
    exe = "python.exe" if _IS_WINDOWS else "python3"
    candidate = (
        os.path.join(sys.base_prefix, exe) if _IS_WINDOWS
        else os.path.join(sys.base_prefix, "bin", exe)
    )
    return candidate if os.path.isfile(candidate) else ""


def _path_python() -> str:
    """Return the first ``python`` found on ``PATH``, or ""."""
    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found:
            return found
    return ""


def in_own_venv() -> bool:
    """True when KhervePY itself is running inside a virtualenv."""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def python_executable(project_root: str | None = None) -> str:
    """Return a usable Python interpreter path for running the project's code.

    A project's **own virtualenv wins** — like a real IDE's project
    interpreter — so each project runs in the environment where its declared
    dependencies live, even when KhervePY itself is launched from a different
    interpreter that happens to be missing them.

    When the project has no venv, KhervePY's *own* virtualenv is deliberately
    **not** used: it holds PyQt6/QScintilla for the editor, not the project's
    dependencies, so a project run there fails on imports that work everywhere
    else. Fall back to the base interpreter that venv was made from, or to
    ``python`` on ``PATH`` — the same interpreter a plain terminal would use.

    Returns "" if none is found.
    """
    venv = project_venv_python(project_root)
    if venv:
        return venv

    if getattr(sys, "frozen", False):
        # sys.executable is KhervePY.exe here, never a real interpreter.
        return _path_python()

    if in_own_venv():
        return _base_python() or _path_python() or sys.executable

    return sys.executable
