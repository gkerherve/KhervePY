"""Process helpers shared across KhervePY.

Two concerns handled here, both mattering mainly for the *frozen* (PyInstaller)
build on Windows:

* **No flashing consoles.** A windowed app has no console, so every child
  console program (``git``, ``cmd``, ``python``) would otherwise pop its own
  console window. ``CREATE_NO_WINDOW`` suppresses that for both
  ``subprocess`` and ``QProcess`` children.
* **A real Python interpreter.** In a frozen build ``sys.executable`` is
  ``KhervePY.exe`` itself, not Python — so Run/Debug/pip must locate an actual
  interpreter instead. On Windows that means stepping around the Microsoft
  Store *app execution alias* (a 0-byte stub in ``WindowsApps`` that shadows
  the real ``python.exe`` on ``PATH``).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import glob
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


def is_store_stub(path: str) -> bool:
    """True when *path* is a Microsoft Store *app execution alias*, not an exe.

    Windows ships 0-byte reparse points in ``%LOCALAPPDATA%\\Microsoft\\
    WindowsApps`` — ``python.exe`` among them — whose only job is to open the
    Store when the app is not installed. That directory sits near the front of
    ``PATH``, so a naive ``shutil.which("python")`` returns the stub and every
    launch fails with "could not start the interpreter".
    """
    if not _IS_WINDOWS or not path:
        return False
    if "\\windowsapps\\" not in path.replace("/", "\\").lower():
        return False
    try:
        return os.path.getsize(path) == 0
    except OSError:
        return True


def _path_pythons() -> list[str]:
    """Every ``python`` on ``PATH``, in ``PATH`` order (stubs included)."""
    names = (("python.exe", "python3.exe") if _IS_WINDOWS
             else ("python3", "python"))
    found: list[str] = []
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        for name in names:
            candidate = os.path.join(os.path.expandvars(directory), name)
            if os.path.isfile(candidate) and candidate not in found:
                found.append(candidate)
    return found


def _registry_pythons() -> list[str]:
    """Interpreters registered under ``SOFTWARE\\Python\\PythonCore``.

    This is what every Windows Python installer writes, so it finds real
    installs that are not on ``PATH`` at all — the common case when someone
    ticked nothing during setup.
    """
    if not _IS_WINDOWS:
        return []
    try:
        import winreg
    except ImportError:
        return []

    found: list[tuple[tuple, str]] = []
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    for root in roots:
        try:
            key = winreg.OpenKey(root, r"SOFTWARE\Python\PythonCore")
        except OSError:
            continue
        with key:
            for index in range(winreg.QueryInfoKey(key)[0]):
                try:
                    version = winreg.EnumKey(key, index)
                    with winreg.OpenKey(
                            key, version + r"\InstallPath") as sub:
                        install = winreg.QueryValue(sub, "")
                except OSError:
                    continue
                exe = os.path.join(install, "python.exe")
                if os.path.isfile(exe):
                    found.append((_version_key(version), exe))
    # Newest interpreter first: 3.13 beats 3.9, and "3.12" beats "3.12-32".
    found.sort(key=lambda item: item[0], reverse=True)
    return [exe for _key, exe in found]


def _version_key(version: str) -> tuple:
    """Sort key for a registry version tag such as ``3.12`` or ``3.12-32``."""
    base, _, suffix = version.partition("-")
    parts = tuple(int(p) if p.isdigit() else 0 for p in base.split("."))
    return parts + (0 if suffix else 1,)


def _wellknown_pythons() -> list[str]:
    """Interpreters in the usual Windows install locations, newest first."""
    if not _IS_WINDOWS:
        return []
    patterns = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     "Programs", "Python", "Python3*", "python.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "Python3*", "python.exe"),
        r"C:\Python3*\python.exe",
    ]
    found: list[str] = []
    for pattern in patterns:
        if not os.path.isabs(pattern):
            continue  # the environment variable it was built from is unset
        found.extend(p for p in glob.glob(pattern) if os.path.isfile(p))
    found.sort(reverse=True)  # Python313 before Python39
    return found


def _path_python() -> str:
    """Return a usable system Python, preferring real installs over stubs.

    Order: real interpreters on ``PATH``, then registered installs, then the
    standard install directories. A Store alias stub is only returned when
    nothing else exists — better a failing launch with a familiar path than no
    path at all.
    """
    stubs: list[str] = []
    for candidate in _path_pythons():
        if is_store_stub(candidate):
            stubs.append(candidate)
        else:
            return candidate

    for candidate in _registry_pythons() + _wellknown_pythons():
        if os.path.isfile(candidate) and not is_store_stub(candidate):
            return candidate

    # Last resort: the launcher, which resolves its own interpreter.
    launcher = shutil.which("py")
    if launcher and not is_store_stub(launcher):
        return launcher
    return stubs[0] if stubs else ""


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
