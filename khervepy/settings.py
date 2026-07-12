"""Persistent settings for KhervePY, backed by ``QSettings``.

Stores the chosen theme, the GitHub personal-access token, recently opened
projects and window geometry. The token is kept in the OS-native settings
store (registry / plist / ini) rather than in the repository.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings

from khervepy import __app_name__, __author__
from khervepy.themes import DEFAULT_THEME


class Settings:
    """Thin, typed façade over ``QSettings``."""

    def __init__(self):
        self._q = QSettings(__author__, __app_name__)

    # --- theme -----------------------------------------------------------
    @property
    def theme(self) -> str:
        return self._q.value("editor/theme", DEFAULT_THEME, type=str)

    @theme.setter
    def theme(self, value: str) -> None:
        self._q.setValue("editor/theme", value)

    # --- font ------------------------------------------------------------
    @property
    def font_size(self) -> int:
        return self._q.value("editor/font_size", 11, type=int)

    @font_size.setter
    def font_size(self, value: int) -> None:
        self._q.setValue("editor/font_size", int(value))

    # --- GitHub ----------------------------------------------------------
    @property
    def github_token(self) -> str:
        return self._q.value("github/token", "", type=str)

    @github_token.setter
    def github_token(self, value: str) -> None:
        self._q.setValue("github/token", value)

    @property
    def github_user(self) -> str:
        return self._q.value("github/user", "", type=str)

    @github_user.setter
    def github_user(self, value: str) -> None:
        self._q.setValue("github/user", value)

    # --- recent projects -------------------------------------------------
    def recent_projects(self) -> list[str]:
        return self._q.value("recent/projects", [], type=list) or []

    def push_recent_project(self, path: str) -> None:
        items = [p for p in self.recent_projects() if p != path]
        items.insert(0, path)
        self._q.setValue("recent/projects", items[:12])

    @property
    def last_project(self) -> str:
        return self._q.value("recent/last_project", "", type=str)

    @last_project.setter
    def last_project(self, value: str) -> None:
        self._q.setValue("recent/last_project", value)

    # --- window ----------------------------------------------------------
    def save_geometry(self, geometry) -> None:
        self._q.setValue("window/geometry", geometry)

    def restore_geometry(self):
        return self._q.value("window/geometry")

    def save_state(self, state) -> None:
        self._q.setValue("window/state", state)

    def restore_state(self):
        return self._q.value("window/state")
