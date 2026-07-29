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

    @property
    def menubar_visible(self) -> bool:
        return self._q.value("window/menubar_visible", True, type=bool)

    @menubar_visible.setter
    def menubar_visible(self, value: bool) -> None:
        self._q.setValue("window/menubar_visible", bool(value))

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

    # --- AI assistant ----------------------------------------------------
    def api_key(self, provider: str) -> str:
        return self._q.value(f"ai/key/{provider}", "", type=str)

    def set_api_key(self, provider: str, key: str) -> None:
        self._q.setValue(f"ai/key/{provider}", key)

    @property
    def ai_provider(self) -> str:
        return self._q.value("ai/provider", "anthropic", type=str)

    @ai_provider.setter
    def ai_provider(self, value: str) -> None:
        self._q.setValue("ai/provider", value)

    def ai_model(self, provider: str) -> str:
        return self._q.value(f"ai/model/{provider}", "", type=str)

    def set_ai_model(self, provider: str, model: str) -> None:
        self._q.setValue(f"ai/model/{provider}", model)

    def ai_models(self, provider: str) -> list[str]:
        return self._q.value(f"ai/models/{provider}", [], type=list) or []

    def set_ai_models(self, provider: str, models: list[str]) -> None:
        self._q.setValue(f"ai/models/{provider}", list(models))

    # --- open editor session ---------------------------------------------
    @property
    def open_files(self) -> list[str]:
        return self._q.value("session/open_files", [], type=list) or []

    @open_files.setter
    def open_files(self, value: list[str]) -> None:
        self._q.setValue("session/open_files", list(value))

    @property
    def active_file(self) -> str:
        return self._q.value("session/active_file", "", type=str)

    @active_file.setter
    def active_file(self, value: str) -> None:
        self._q.setValue("session/active_file", value)

    # --- window ----------------------------------------------------------
    def save_geometry(self, geometry) -> None:
        self._q.setValue("window/geometry", geometry)

    def restore_geometry(self):
        return self._q.value("window/geometry")

    def save_state(self, state) -> None:
        self._q.setValue("window/state", state)

    def restore_state(self):
        return self._q.value("window/state")

    # --- compact ("mini") mode window ------------------------------------
    def save_compact_geometry(self, geometry) -> None:
        self._q.setValue("window/compact_geometry", geometry)

    def restore_compact_geometry(self):
        return self._q.value("window/compact_geometry")

    # The key is versioned: a layout saved by an older KhervePY pins the docks
    # that version put in the cockpit (Terminal on the left), and restoring it
    # would silently undo the current arrangement. A new key starts clean.
    _COMPACT_STATE_KEY = "window/compact_state_v2"

    def save_compact_state(self, state) -> None:
        self._q.setValue(self._COMPACT_STATE_KEY, state)

    def restore_compact_state(self):
        return self._q.value(self._COMPACT_STATE_KEY)
