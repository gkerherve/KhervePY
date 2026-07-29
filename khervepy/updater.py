"""Check GitHub for a newer KhervePY and install it.

KhervePY ships as a Windows installer published on GitHub Releases, so an
update is: read the latest release, compare its tag with ``__version__``, and —
if the user says yes — download the installer and hand over to it.

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

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from urllib import error, request

from khervepy import __version__

REPO = "gkerherve/KhervePY"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
TIMEOUT = 10


@dataclass(frozen=True)
class Release:
    """The latest published release, as far as updating cares about it."""

    version: str          # "0.35.0"
    tag: str              # "v0.35.0"
    page: str             # html_url, for "what changed?"
    notes: str            # release body
    installer: str = ""   # download URL of the Windows installer, if any
    archive: str = ""     # download URL of the portable zip, if any


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


def fetch_latest(token: str = "", timeout: int = TIMEOUT) -> Release | None:
    """Read the latest release from GitHub, or None if it cannot be read.

    A token is optional and only lifts the anonymous rate limit; checking one
    public repo occasionally stays well inside it either way.
    """
    req = request.Request(LATEST_URL)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "KhervePY")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, ValueError, OSError):
        # Offline, rate-limited, or GitHub is having a day. Not worth a dialog.
        return None

    tag = payload.get("tag_name") or ""
    installer = archive = ""
    for asset in payload.get("assets", []):
        name = (asset.get("name") or "").lower()
        url = asset.get("browser_download_url") or ""
        # Prefer the version-less installer: it is the one the website's
        # /releases/latest/download/ link points at, so it is always present.
        if name.endswith(".exe") and (not installer or name == "khervepy-setup.exe"):
            installer = url
        elif name.endswith(".zip") and not archive:
            archive = url
    return Release(
        version=tag.lstrip("vV"),
        tag=tag,
        page=payload.get("html_url") or RELEASES_PAGE,
        notes=(payload.get("body") or "").strip(),
        installer=installer,
        archive=archive,
    )


def download(url: str, on_progress=None, timeout: int = 60) -> str:
    """Download *url* into a temporary file and return its path.

    *on_progress* is called with (bytes_so_far, total_or_zero) and may return
    False to abort, which raises ``InterruptedError``.
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
    return target


def is_frozen() -> bool:
    """True in the PyInstaller build, where an installer can take over."""
    return bool(getattr(sys, "frozen", False))


def launch_installer(path: str) -> bool:
    """Start the downloaded installer detached, so it outlives this process.

    The installer replaces the files this very process is running from, so it
    must not be a child that dies with us.
    """
    from PyQt6.QtCore import QProcess

    return QProcess.startDetached(path, [])
