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


# --- per-project interpreter choice -----------------------------------------
# The main window loads the user's pick for the open project from settings and
# registers it here, so every caller of ``python_executable`` (Run, Debug, pip,
# requirements check) agrees without each one having to know about settings.
_OVERRIDES: dict[str, str] = {}


def _key(project_root: str | None) -> str:
    return os.path.normcase(os.path.abspath(project_root)) if project_root else ""


def set_interpreter_override(project_root: str | None, path: str) -> None:
    """Pin *path* as the interpreter for *project_root* ("" clears the pin)."""
    key = _key(project_root)
    if not key:
        return
    if path:
        _OVERRIDES[key] = path
    else:
        _OVERRIDES.pop(key, None)


def interpreter_override(project_root: str | None) -> str:
    """The pinned interpreter for *project_root*, or "" if none (or it vanished)."""
    path = _OVERRIDES.get(_key(project_root), "")
    return path if path and os.path.isfile(path) else ""


def interpreter_candidates(project_root: str | None) -> list[str]:
    """Every Python worth offering in the picker, best-guess first, de-duplicated.

    Project virtualenvs, then ``PATH``, then the places each tool installs to:
    Homebrew, the python.org framework, pyenv, conda/mamba, uv and — on
    Windows — the registry and the standard install directories.
    """
    found: list[str] = []
    real_seen: set[str] = set()

    def add(path: str) -> None:
        if not (path and os.path.isfile(path) and os.access(path, os.X_OK)
                and not is_store_stub(path) and path not in found):
            return
        # python3, python3.13 and /usr/local/bin/python3 are often one binary;
        # list it once. (A venv's python resolves to its base, so venvs are
        # exempt — they are different environments.)
        is_venv = os.path.isfile(os.path.join(
            os.path.dirname(os.path.dirname(path)), "pyvenv.cfg"))
        real = os.path.realpath(path)
        if not is_venv:
            if real in real_seen:
                return
            real_seen.add(real)
        found.append(path)

    sub, exe = ("Scripts", "python.exe") if _IS_WINDOWS else ("bin", "python")
    if project_root:
        for name in ("venv", ".venv", "env", ".env"):
            add(os.path.join(project_root, name, sub, exe))
    for path in _path_pythons():
        add(path)
    for path in _registry_pythons() + _wellknown_pythons():
        add(path)
    if not _IS_WINDOWS:
        home = os.path.expanduser("~")
        patterns = [
            "/opt/homebrew/bin/python3*", "/usr/local/bin/python3*",
            "/opt/homebrew/opt/python@*/bin/python3*",
            "/Library/Frameworks/Python.framework/Versions/*/bin/python3",
            "/opt/local/bin/python3*",
            os.path.join(home, ".pyenv/versions/*/bin/python"),
            os.path.join(home, ".local/share/uv/python/*/bin/python3"),
        ]
        # /usr/bin/python3 is a shim that pops an "install the Command Line
        # Tools" prompt when probed on a Mac that has none; only offer it then.
        if sys.platform != "darwin" or os.path.isdir("/Library/Developer/CommandLineTools"):
            patterns.append("/usr/bin/python3")
        for base in ("miniconda3", "anaconda3", "miniforge3", "mambaforge",
                     "opt/anaconda3", ".conda"):
            patterns.append(os.path.join(home, base, "bin/python"))
            patterns.append(os.path.join(home, base, "envs/*/bin/python"))
        for pattern in patterns:
            for path in sorted(glob.glob(pattern)):
                # python3-config, python3.13-config … are not interpreters.
                base = os.path.basename(path)
                if "config" not in base and "intel64" not in base:
                    add(path)
    return found


def _version_from_path(path: str) -> str:
    """Best-effort ``3.13`` from the path alone — never runs the interpreter."""
    import re

    real = os.path.realpath(path).replace("\\", "/")
    for pattern in (r"/Versions/(\d+\.\d+)/", r"python@(\d+\.\d+)", r"/python(\d+\.\d+)",
                    r"/Python(\d)(\d+)/"):
        m = re.search(pattern, real) or re.search(pattern, path.replace("\\", "/"))
        if m:
            return ".".join(m.groups())
    return ""


def interpreter_label(path: str, project_root: str | None = None,
                      probe: bool = True) -> str:
    """A human name: ``Python 3.13.1 (.venv)`` / ``Python 3.12.6 (Homebrew)``.

    Reads ``pyvenv.cfg`` for virtualenvs (instant); otherwise asks the
    interpreter, with a short timeout so a broken one cannot hang the UI.
    ``probe=False`` never starts a process (safe on the GUI thread): the
    version then comes from the path, or is left out.
    """
    version = ""
    cfg = os.path.join(os.path.dirname(os.path.dirname(path)), "pyvenv.cfg")
    if os.path.isfile(cfg):
        try:
            with open(cfg, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    key, _, value = line.partition("=")
                    if key.strip() in ("version", "version_info"):
                        version = ".".join(value.strip().split(".")[:3])
                        break
        except OSError:
            pass
    if not version and not probe:
        version = _version_from_path(path)
        where = _where(path, project_root)
        return "Python" + (f" {version}" if version else "") + (f" ({where})" if where else "")
    if not version:
        try:
            out = subprocess.run([path, "--version"], capture_output=True,
                                 text=True, timeout=4, **{
                                     k: v for k, v in subprocess_flags().items()
                                     if k in ("creationflags", "startupinfo")})
            version = (out.stdout or out.stderr).strip().replace("Python ", "")
        except (OSError, subprocess.SubprocessError):
            version = "?"
    where = _where(path, project_root)
    return f"Python {version}" + (f" ({where})" if where else "")


def _where(path: str, project_root: str | None) -> str:
    home = os.path.expanduser("~")
    parent = os.path.dirname(os.path.dirname(path))
    if os.path.isfile(os.path.join(parent, "pyvenv.cfg")):
        name = os.path.basename(parent)
        if project_root and os.path.dirname(parent) == project_root.rstrip("/\\"):
            return name
        return f"venv {name}"
    if "/envs/" in path.replace("\\", "/"):
        return "conda " + os.path.basename(parent)
    real = os.path.realpath(path)
    for token, name in (("/library/frameworks/python.framework", "python.org"), ("homebrew", "Homebrew"),
                        ("cellar", "Homebrew"), (".pyenv", "pyenv"), ("/uv/", "uv"),
                        ("conda", "conda"), ("miniforge", "conda"),
                        ("/opt/local", "MacPorts"), ("/usr/bin", "system"),
                        ("applications/xcode", "system"),
                        ("commandlinetools", "system")):
        if token in real.lower():
            return name
    return "~" + path[len(home):] if path.startswith(home) else ""


def python_executable(project_root: str | None = None) -> str:
    """Return a usable Python interpreter path for running the project's code.

    An interpreter the user **picked for the project** (status bar ▸ Python)
    wins over everything. Otherwise a project's **own virtualenv wins** — like a real IDE's project
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
    pinned = interpreter_override(project_root)
    if pinned:
        return pinned

    venv = project_venv_python(project_root)
    if venv:
        return venv

    if getattr(sys, "frozen", False):
        # sys.executable is KhervePY.exe here, never a real interpreter.
        return _path_python()

    if in_own_venv():
        return _base_python() or _path_python() or sys.executable

    return sys.executable
