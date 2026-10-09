"""Run configurations: what to run, with which arguments, where, and how.

Pure data and command building (no Qt), so it can be tested headless. A
configuration is one of three kinds:

* ``script`` — ``python -u <file> <args>``; an empty target means "the file in
  the active editor tab" (the built-in *Current file* configuration);
* ``module`` — ``python -u -m <module> <args>`` (``http.server``, ``mypkg.cli``…);
* ``pytest`` — ``python -u -m pytest <target> <args>``; an empty target runs the
  whole project.

Arguments, working directory and environment values understand three macros:
``$FILE`` (the active file), ``$FILEDIR`` and ``$PROJECT``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import asdict, dataclass, field

KINDS = ("script", "module", "pytest")
CURRENT_FILE = "Current file"
RUN_TESTS = "Run tests (pytest)"


@dataclass
class RunConfig:
    name: str
    kind: str = "script"
    target: str = ""          # script path | module name | pytest path/expression
    args: str = ""            # shell-style: --flag "two words"
    env: str = ""             # one KEY=VALUE per line
    cwd: str = ""             # blank = the project root
    interpreter: str = ""     # blank = the project's interpreter
    in_terminal: bool = False  # run in the integrated terminal (stdin works)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "RunConfig":
        known = {k: raw[k] for k in cls.__dataclass_fields__ if k in raw}
        known.setdefault("name", "Unnamed")
        cfg = cls(**known)
        if cfg.kind not in KINDS:
            cfg.kind = "script"
        return cfg

    @property
    def is_current_file(self) -> bool:
        return self.kind == "script" and not self.target


def builtin_configs() -> list[RunConfig]:
    """The two configurations that always exist and cannot be deleted."""
    return [RunConfig(CURRENT_FILE), RunConfig(RUN_TESTS, kind="pytest")]


@dataclass
class Command:
    """A fully resolved launch: ready for QProcess or for a shell line."""

    python: str
    args: list[str]            # everything after the interpreter
    cwd: str
    env: dict = field(default_factory=dict)   # extras to add to the environment
    display: str = ""          # the line echoed in the Output panel

    @property
    def argv(self) -> list[str]:
        return [self.python, *self.args]


def _expand(text: str, current_file: str, project_root: str) -> str:
    return (text.replace("$FILEDIR", os.path.dirname(current_file) if current_file else "")
                .replace("$FILE", current_file or "")
                .replace("$PROJECT", project_root or ""))


def split_args(text: str) -> list[str]:
    """Shell-style split that does not choke on a half-typed quote."""
    try:
        return shlex.split(text, posix=os.name != "nt")
    except ValueError:
        return text.split()


def parse_env(text: str) -> dict:
    out = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def validate(cfg: RunConfig, current_file: str) -> str:
    """Return a reason this cannot run, or "" when it can."""
    if cfg.kind == "script":
        target = cfg.target or current_file
        if not target:
            return "Open a Python file first (or set a script in the configuration)."
        if not target.endswith((".py", ".pyw")):
            return f"Run supports .py files, not {os.path.basename(target)}."
    elif cfg.kind == "module" and not cfg.target.strip():
        return "The configuration has no module name."
    return ""


def build_command(cfg: RunConfig, python: str, project_root: str,
                  current_file: str = "") -> Command:
    """Resolve *cfg* against the project: absolute script, cwd, env, argv."""
    def exp(text: str) -> str:
        return _expand(text, current_file, project_root)

    py = cfg.interpreter or python
    extra = [exp(a) for a in split_args(cfg.args)]
    if cfg.kind == "module":
        args = ["-u", "-m", cfg.target.strip(), *extra]
    elif cfg.kind == "pytest":
        targets = [exp(a) for a in split_args(cfg.target)]
        args = ["-u", "-m", "pytest", *targets, *extra]
    else:
        script = exp(cfg.target) if cfg.target else current_file
        if script and not os.path.isabs(script):
            script = os.path.join(project_root, script)
        args = ["-u", script, *extra]

    cwd = exp(cfg.cwd).strip() if cfg.cwd.strip() else ""
    if cwd:
        cwd = os.path.expanduser(cwd)
        if not os.path.isabs(cwd):
            cwd = os.path.join(project_root, cwd)
    else:
        cwd = project_root or (os.path.dirname(args[1]) if cfg.kind == "script" else os.getcwd())

    env = {k: exp(v) for k, v in parse_env(cfg.env).items()}
    cmd = Command(python=py, args=args, cwd=cwd, env=env)
    cmd.display = shell_line(cmd, with_cwd=False)
    return cmd


def shell_line(cmd: Command, with_cwd: bool = True) -> str:
    """The command as one line for a shell (quoted for the platform)."""
    if os.name == "nt":
        line = subprocess.list2cmdline(cmd.argv)
        envs = "".join(f'set "{k}={v}" && ' for k, v in cmd.env.items())
        head = f'cd /d "{cmd.cwd}" && ' if with_cwd else ""
        return head + envs + line
    q = shlex.quote
    envs = "".join(f"{k}={q(v)} " for k, v in cmd.env.items())
    head = f"cd {q(cmd.cwd)} && " if with_cwd else ""
    return head + envs + " ".join(q(a) for a in cmd.argv)
