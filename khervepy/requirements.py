"""requirements.txt inspection — parse a requirements file and report which
of its packages are missing from a given interpreter.

This complements the *reactive* missing-module handler (which only fires when a
run crashes with ``ModuleNotFoundError``): some dependencies degrade gracefully
and never crash — e.g. a toolbar whose icons simply fall back to text when
``qtawesome`` is absent — so nothing is ever raised. A *proactive* check reads
the declared requirements and compares them against the interpreter's installed
distributions, catching those silent gaps before they surprise the user.

No Qt here, so the module stays importable headless (for tooling and tests).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from khervepy.proc import subprocess_flags

#: Leading distribution name in a PEP 508 requirement (before any extras,
#: specifier, marker or URL).
_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
#: An inline comment starts at the first ``#`` preceded by whitespace.
_INLINE_COMMENT_RE = re.compile(r"\s+#.*$")


@dataclass(frozen=True)
class Requirement:
    """One dependency line from a requirements file."""

    raw: str          #: the requirement as pip should receive it (no comment)
    name: str         #: the distribution name (e.g. "qtawesome")
    specifier: str    #: the version constraint, if any (e.g. ">=1.3")


def normalize(name: str) -> str:
    """PEP 503 canonical form: lower-case, runs of ``-_.`` collapsed to ``-``."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements(path: str) -> list[Requirement]:
    """Parse *path* into a list of :class:`Requirement`.

    Handles blank lines, full-line and inline comments, environment markers,
    extras (``pkg[extra]``) and the ``name @ url`` form. Skips option lines
    (``-r``/``-e``/``--hash`` …) and bare URLs, which carry no simple name.
    """
    reqs: list[Requirement] = []
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return reqs

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = _INLINE_COMMENT_RE.sub("", line).strip()
        if not line:
            continue
        # Drop any environment marker (";" onwards); keep the "name @ url" head.
        spec_part = line.split(";", 1)[0].strip()
        head = spec_part.split("@", 1)[0].strip()
        # A bare URL with no leading name (git+https://…, https://…) is skipped.
        if "://" in head:
            continue
        m = _NAME_RE.match(head)
        if not m:
            continue
        name = m.group(1)
        specifier = head[m.end():].strip()
        # Strip an extras group like "[socks]" that can precede the specifier.
        if specifier.startswith("["):
            specifier = specifier.split("]", 1)[-1].strip()
        reqs.append(Requirement(raw=spec_part, name=name, specifier=specifier))
    return reqs


def installed_distributions(python_exe: str) -> dict[str, str]:
    """Map normalized distribution name -> version for *python_exe*.

    Queries the target interpreter via ``pip list`` so the answer reflects the
    environment the script would actually run in (which may be a project venv
    distinct from the one running KhervePY).
    """
    try:
        out = subprocess.run(
            [python_exe, "-m", "pip", "list", "--format=freeze"],
            capture_output=True, timeout=60, **subprocess_flags(),
        ).stdout or ""
    except (subprocess.SubprocessError, OSError):
        return {}
    installed: dict[str, str] = {}
    for row in out.splitlines():
        row = row.strip()
        if not row or row.startswith("#") or "==" not in row:
            continue
        name, _, version = row.partition("==")
        installed[normalize(name)] = version.strip()
    return installed


@dataclass
class CheckResult:
    """Outcome of comparing a requirements file against an interpreter."""

    path: str
    requirements: list[Requirement]
    installed: dict[str, str]
    missing: list[Requirement]
    present: list[tuple[Requirement, str]]  #: (requirement, installed version)


def check_requirements(path: str, python_exe: str) -> CheckResult:
    """Compare the requirements in *path* against *python_exe*'s packages."""
    reqs = parse_requirements(path)
    installed = installed_distributions(python_exe)
    missing = [r for r in reqs if normalize(r.name) not in installed]
    present = [
        (r, installed[normalize(r.name)])
        for r in reqs if normalize(r.name) in installed
    ]
    return CheckResult(path=path, requirements=reqs, installed=installed,
                       missing=missing, present=present)


def find_requirements_file(project_root: str) -> str | None:
    """Return the project's ``requirements.txt`` path, or ``None`` if absent."""
    candidate = os.path.join(project_root, "requirements.txt")
    return candidate if os.path.isfile(candidate) else None
