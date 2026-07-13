"""Git and GitHub plumbing for KhervePY.

Local repository operations shell out to the ``git`` executable; GitHub API
operations (fork, list repositories, current user) use the REST API over the
standard library so the app has no networking dependencies.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional
from urllib import error, request

GITHUB_API = "https://api.github.com"


class GitError(RuntimeError):
    """Raised when a git command exits non-zero."""


@dataclass
class GitStatus:
    branch: str
    ahead: int
    behind: int
    staged: list[tuple[str, str]]
    unstaged: list[tuple[str, str]]
    untracked: list[str]

    @property
    def is_clean(self) -> bool:
        return not (self.staged or self.unstaged or self.untracked)


# --- Local git --------------------------------------------------------------
def run_git(args: list[str], cwd: str, check: bool = True) -> str:
    """Run ``git <args>`` inside ``cwd`` and return stdout."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.strip() or proc.stdout.strip() or "git failed")
    return proc.stdout


def is_repo(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    try:
        out = run_git(["rev-parse", "--is-inside-work-tree"], path)
        return out.strip() == "true"
    except GitError:
        return False


def repo_root(path: str) -> Optional[str]:
    try:
        return run_git(["rev-parse", "--show-toplevel"], path).strip()
    except GitError:
        return None


def current_branch(path: str) -> str:
    try:
        return run_git(["rev-parse", "--abbrev-ref", "HEAD"], path).strip()
    except GitError:
        return ""


def status(path: str) -> GitStatus:
    """Parse ``git status --porcelain=v1 -b`` into a structured result."""
    out = run_git(["status", "--porcelain=v1", "-b"], path)
    branch, ahead, behind = "", 0, 0
    staged: list[tuple[str, str]] = []
    unstaged: list[tuple[str, str]] = []
    untracked: list[str] = []

    for line in out.splitlines():
        if line.startswith("##"):
            head = line[3:]
            branch = head.split("...")[0].strip()
            m_a = re.search(r"ahead (\d+)", head)
            m_b = re.search(r"behind (\d+)", head)
            ahead = int(m_a.group(1)) if m_a else 0
            behind = int(m_b.group(1)) if m_b else 0
            continue
        if len(line) < 3:
            continue
        x, y, name = line[0], line[1], line[3:]
        if x == "?" and y == "?":
            untracked.append(name)
            continue
        if x != " " and x != "?":
            staged.append((x, name))
        if y != " " and y != "?":
            unstaged.append((y, name))
    return GitStatus(branch, ahead, behind, staged, unstaged, untracked)


def branches(path: str) -> list[str]:
    out = run_git(["branch", "--format=%(refname:short)"], path)
    return [b.strip() for b in out.splitlines() if b.strip()]


def remote_branches(path: str) -> list[str]:
    """Return remote-tracking branches (e.g. ``origin/main``), minus HEAD."""
    out = run_git(["branch", "-r", "--format=%(refname:short)"], path, check=False)
    return [
        b.strip() for b in out.splitlines()
        if b.strip() and "->" not in b
    ]


def init(path: str) -> None:
    run_git(["init"], path)


def fetch(path: str, remote: str = "origin") -> str:
    return run_git(["fetch", remote], path, check=False)


def checkout_track(path: str, remote_branch: str) -> None:
    """Check out a remote branch, creating a local tracking branch for it.

    Falls back to a plain checkout if the local branch already exists.
    """
    local = remote_branch.split("/", 1)[1] if "/" in remote_branch else remote_branch
    if local in branches(path):
        run_git(["checkout", local], path)
        return
    run_git(["checkout", "--track", remote_branch], path)


def stage(path: str, files: list[str]) -> None:
    run_git(["add", "--", *files], path)


def stage_all(path: str) -> None:
    run_git(["add", "-A"], path)


def unstage(path: str, files: list[str]) -> None:
    run_git(["reset", "HEAD", "--", *files], path)


def commit(path: str, message: str) -> str:
    return run_git(["commit", "-m", message], path)


def checkout(path: str, branch: str, create: bool = False) -> None:
    args = ["checkout", "-b", branch] if create else ["checkout", branch]
    run_git(args, path)


def pull(path: str, remote: str = "origin", branch: Optional[str] = None) -> str:
    args = ["pull", remote]
    if branch:
        args.append(branch)
    return run_git(args, path)


def push(path: str, remote: str = "origin", branch: Optional[str] = None,
         set_upstream: bool = False) -> str:
    args = ["push"]
    if set_upstream and branch:
        args += ["-u", remote, branch]
    elif branch:
        args += [remote, branch]
    else:
        args.append(remote)
    return run_git(args, path)


def log(path: str, limit: int = 30) -> list[tuple[str, str, str]]:
    """Return ``(short_hash, author, subject)`` tuples for recent commits."""
    fmt = "%h\x1f%an\x1f%s"
    out = run_git(["log", f"-{limit}", f"--pretty=format:{fmt}"], path, check=False)
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def log_entries(path: str, limit: int = 300) -> list[dict]:
    """Return recent commits as dicts: hash, author, date, subject, refs."""
    fmt = "%h\x1f%an\x1f%ad\x1f%s\x1f%D"
    out = run_git(
        ["log", f"-{limit}", "--date=short", f"--pretty=format:{fmt}"],
        path, check=False,
    )
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) >= 4:
            rows.append({
                "hash": parts[0],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3],
                "refs": parts[4] if len(parts) > 4 else "",
            })
    return rows


def show_commit(path: str, rev: str) -> str:
    """Return ``git show`` output (patch) for a single revision."""
    return run_git(["show", "--stat", "--patch", rev], path, check=False)


def commit_files(path: str, rev: str) -> list[tuple[str, str]]:
    """Return ``(status, filepath)`` for files changed in ``rev``."""
    out = run_git(
        ["show", "--name-status", "--pretty=format:", rev], path, check=False
    )
    files = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append((parts[0][0], parts[-1]))
    return files


def commit_file_diff(path: str, rev: str, file: str) -> str:
    """Return the patch for a single ``file`` as changed in ``rev``."""
    return run_git(["show", rev, "--", file], path, check=False)


def log_graph(path: str, all_branches: bool = True, limit: int = 500) -> list[dict]:
    """Return commits (topological order) with parents and ref decorations.

    Each entry: ``full`` (full hash), ``hash`` (short), ``parents`` (list of
    full hashes), ``author``, ``date``, ``subject``, ``refs``.
    """
    fmt = "%H\x1f%h\x1f%P\x1f%an\x1f%ad\x1f%s\x1f%D"
    args = ["log", f"-{limit}", "--date=short", "--topo-order",
            f"--pretty=format:{fmt}"]
    if all_branches:
        args.insert(1, "--all")
    out = run_git(args, path, check=False)
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) >= 6:
            rows.append({
                "full": parts[0],
                "hash": parts[1],
                "parents": parts[2].split() if parts[2] else [],
                "author": parts[3],
                "date": parts[4],
                "subject": parts[5],
                "refs": parts[6] if len(parts) > 6 else "",
            })
    return rows


def diff(path: str, staged: bool = False) -> str:
    args = ["diff", "--cached"] if staged else ["diff"]
    return run_git(args, path, check=False)


def diff_file(path: str, file: str, staged: bool = False) -> str:
    """Return the unified diff for a single ``file`` within the repo.

    Falls back to an ``--no-index`` diff against /dev/null for untracked files
    so newly created files still show their contents as additions.
    """
    args = ["diff"]
    if staged:
        args.append("--cached")
    args += ["--", file]
    out = run_git(args, path, check=False)
    if out.strip():
        return out
    # Untracked / new file: diff against nothing.
    proc = subprocess.run(
        ["git", "diff", "--no-index", "--", os.devnull, file],
        cwd=path, capture_output=True, text=True,
    )
    return proc.stdout or "(no changes to show)"


def clone(url: str, dest: str, token: str = "") -> str:
    """Clone ``url`` into ``dest``. A token is injected for private HTTPS repos."""
    if token and url.startswith("https://github.com/"):
        url = url.replace("https://", f"https://{token}@", 1)
    parent = os.path.dirname(dest) or "."
    os.makedirs(parent, exist_ok=True)
    proc = subprocess.run(
        ["git", "clone", url, dest],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or "clone failed")
    return proc.stdout + proc.stderr


def remote_url(path: str, remote: str = "origin") -> str:
    try:
        return run_git(["remote", "get-url", remote], path).strip()
    except GitError:
        return ""


# --- GitHub REST API --------------------------------------------------------
def _api(method: str, endpoint: str, token: str, payload: dict | None = None) -> dict:
    url = endpoint if endpoint.startswith("http") else f"{GITHUB_API}{endpoint}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "KhervePY")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            msg = json.loads(detail).get("message", detail)
        except Exception:
            msg = detail
        raise GitError(f"GitHub API {exc.code}: {msg}") from exc
    except error.URLError as exc:
        raise GitError(f"Network error: {exc.reason}") from exc


def github_user(token: str) -> dict:
    """Return the authenticated user's profile."""
    return _api("GET", "/user", token)


def list_user_repos(token: str, per_page: int = 100) -> list[dict]:
    """List repositories the token can access, most recently pushed first."""
    return _api(
        "GET",
        f"/user/repos?per_page={per_page}&sort=pushed&affiliation=owner,collaborator,organization_member",
        token,
    )


def parse_owner_repo(url: str) -> tuple[str, str]:
    """Extract ``(owner, repo)`` from an https or ssh GitHub URL."""
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url)
    if not m:
        raise GitError(f"Not a GitHub URL: {url}")
    return m.group(1), m.group(2)


def fork_repo(url: str, token: str) -> dict:
    """Fork the GitHub repo at ``url`` into the authenticated account."""
    if not token:
        raise GitError("A GitHub token is required to fork a repository.")
    owner, repo = parse_owner_repo(url)
    return _api("POST", f"/repos/{owner}/{repo}/forks", token, payload={})
