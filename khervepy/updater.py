"""Check GitHub for a newer KhervePY and install it.

KhervePY ships as a Windows installer and as macOS disk images published on
GitHub Releases, so an update is: read the latest release, compare its tag with
``__version__``, and — if the user says yes — download the installer (or the
DMG for this Mac's architecture) and hand over to it.

On Windows that is ``releases/latest``. On macOS the DMGs live on separate
``macos-v<ver>`` releases that are never marked "latest" (they would steal
``releases/latest/download/KhervePY-Setup.exe`` from the Windows installer),
so the Mac check reads the release list instead.

Two rules shape this module:

* **Never interrupt.** The startup check is quiet: it runs on a worker thread,
  at most once a day, and says nothing at all unless there is something newer.
  A failed check is not an error the user needs to hear about.
* **Never update behind the user's back.** Nothing is downloaded, and nothing
  is launched, without an explicit click.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from urllib import error, request

from khervepy import __version__

REPO = "gkerherve/KhervePY"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
TIMEOUT = 10
IS_MAC = sys.platform == "darwin"


@dataclass(frozen=True)
class Release:
    """The latest published release, as far as updating cares about it."""

    version: str          # "0.35.0"
    tag: str              # "v0.35.0"
    page: str             # html_url, for "what changed?"
    notes: str            # release body
    installer: str = ""   # download URL of the Windows installer / macOS DMG
    archive: str = ""     # download URL of the portable zip, if any
    sha256: str = ""      # expected SHA-256 of ``installer`` when GitHub says


def parse_version(text: str) -> tuple[int, ...]:
    """``"v0.35.1"`` -> ``(0, 35, 1)``; unparseable text sorts as oldest.

    Only the leading numeric run is compared, so a ``-rc1`` or ``+build``
    suffix does not make a release look newer than its own final.
    """
    numbers = re.findall(r"\d+", (text or "").split("+")[0].split("-")[0])
    return tuple(int(n) for n in numbers) or (0,)


def is_newer(candidate: str, current: str = __version__) -> bool:
    """True when *candidate* is a strictly later version than *current*."""
    new, old = parse_version(candidate), parse_version(current)
    # Pad so 0.35 and 0.35.0 compare equal rather than by length.
    width = max(len(new), len(old))
    return new + (0,) * (width - len(new)) > old + (0,) * (width - len(old))


def mac_arch() -> str:
    """``"arm64"`` or ``"x86_64"`` — the DMG this Mac should get.

    A process running under Rosetta reports x86_64 even on Apple Silicon; it
    should still be offered the native arm64 image.
    """
    if platform.machine() == "arm64":
        return "arm64"
    try:
        out = subprocess.run(["sysctl", "-n", "sysctl.proc_translated"],
                             capture_output=True, text=True, timeout=3).stdout
        if out.strip() == "1":
            return "arm64"
    except (OSError, subprocess.SubprocessError):
        pass
    return "x86_64"


def _get_json(url: str, token: str, timeout: int):
    req = request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "KhervePY")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _release_from(payload: dict) -> Release:
    tag = payload.get("tag_name") or ""
    installer = archive = sha256 = ""
    arch = mac_arch() if IS_MAC else ""
    for asset in payload.get("assets", []):
        name = (asset.get("name") or "").lower()
        url = asset.get("browser_download_url") or ""
        if IS_MAC:
            # The versioned DMG for this architecture; the stable-name copy
            # (KhervePY-macOS-<arch>.dmg) is the fallback.
            if name.endswith(f"-macos-{arch}.dmg"):
                if not installer or name != f"khervepy-macos-{arch}.dmg":
                    installer = url
                    digest = asset.get("digest") or ""
                    sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
            continue
        # Prefer the version-less installer: it is the one the website's
        # /releases/latest/download/ link points at, so it is always present.
        if name.endswith(".exe") and (not installer or name == "khervepy-setup.exe"):
            installer = url
        elif name.endswith(".zip") and not archive:
            archive = url
    return Release(
        version=re.sub(r"^[A-Za-z-]*?[vV]", "", tag) if IS_MAC else tag.lstrip("vV"),
        tag=tag,
        page=payload.get("html_url") or RELEASES_PAGE,
        notes=(payload.get("body") or "").strip(),
        installer=installer,
        archive=archive,
        sha256=sha256,
    )


def fetch_latest(token: str = "", timeout: int = TIMEOUT) -> Release | None:
    """Read the newest release from GitHub, or None if it cannot be read.

    A token is optional and only lifts the anonymous rate limit; checking one
    public repo occasionally stays well inside it either way.

    On macOS the newest release *that carries a DMG for this Mac* wins, since
    the Windows release (``releases/latest``) has none.
    """
    try:
        if not IS_MAC:
            return _release_from(_get_json(LATEST_URL, token, timeout))
        best: Release | None = None
        for payload in _get_json(RELEASES_URL, token, timeout):
            if payload.get("draft") or payload.get("prerelease"):
                continue
            release = _release_from(payload)
            if release.installer and (
                    best is None
                    or parse_version(release.version) > parse_version(best.version)):
                best = release
        return best
    except (error.URLError, TimeoutError, ValueError, OSError):
        # Offline, rate-limited, or GitHub is having a day. Not worth a dialog.
        return None


def download(url: str, on_progress=None, timeout: int = 60,
             sha256: str = "") -> str:
    """Download *url* into a temporary file and return its path.

    *on_progress* is called with (bytes_so_far, total_or_zero) and may return
    False to abort, which raises ``InterruptedError``. When *sha256* is given
    the file must match it, or ``ValueError`` is raised and the file removed.
    """
    req = request.Request(url)
    req.add_header("User-Agent", "KhervePY")
    folder = tempfile.mkdtemp(prefix="khervepy-update-")
    target = os.path.join(folder, os.path.basename(url.split("?")[0]) or "update")

    with request.urlopen(req, timeout=timeout) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with open(target, "wb") as handle:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                if on_progress is not None and on_progress(done, total) is False:
                    raise InterruptedError("cancelled")
    if sha256:
        digest = hashlib.sha256()
        with open(target, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != sha256.lower():
            os.remove(target)
            raise ValueError("the download is corrupt (SHA-256 mismatch)")
    return target


def is_frozen() -> bool:
    """True in the PyInstaller build, where an installer can take over."""
    return bool(getattr(sys, "frozen", False))


def install_prompt() -> str:
    """What the "Install now?" dialog should tell the user will happen."""
    if IS_MAC:
        return ("The disk image will open. Drag KhervePY onto Applications "
                "to replace the old copy, so KhervePY will close.")
    return ("The installer needs to replace the running program, so "
            "KhervePY will close.")


def launch_installer(path: str) -> bool:
    """Start the downloaded installer detached, so it outlives this process.

    The installer replaces the files this very process is running from, so it
    must not be a child that dies with us. On macOS "installing" is opening
    the DMG in Finder: the app was downloaded by KhervePY itself, so it
    carries no quarantine flag.
    """
    if IS_MAC:
        return subprocess.run(["open", path]).returncode == 0

    from PyQt6.QtCore import QProcess

    return QProcess.startDetached(path, [])
