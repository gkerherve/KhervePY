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

import hashlib
import json
import os

from PyQt6.QtCore import QSettings

from khervepy import __app_name__, __author__
from khervepy import secrets
from khervepy.themes import DEFAULT_THEME


class Settings:
    """Thin, typed façade over ``QSettings``."""

    def __init__(self):
        # KHERVEPY_SETTINGS_FILE points the app at a throw-away .ini, which is how
        # the self-test and the tests keep away from the user's real preferences.
        # (QSettings.setDefaultFormat does NOT do this: the (org, app)
        # constructor stays on the native store — the plist — on macOS.)
        override = os.environ.get("KHERVEPY_SETTINGS_FILE")
        if override:
            self._q = QSettings(override, QSettings.Format.IniFormat)
        else:
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

    # --- updates ---------------------------------------------------------
    @property
    def check_updates(self) -> bool:
        """Whether to look for a new release quietly on start-up."""
        return self._q.value("update/check", True, type=bool)

    @check_updates.setter
    def check_updates(self, value: bool) -> None:
        self._q.setValue("update/check", bool(value))

    @property
    def last_update_check(self) -> str:
        """ISO date of the last start-up check, so it happens once a day."""
        return self._q.value("update/last_check", "", type=str)

    @last_update_check.setter
    def last_update_check(self, value: str) -> None:
        self._q.setValue("update/last_check", value)

    @property
    def skipped_version(self) -> str:
        """A version the user chose to skip; never announced again."""
        return self._q.value("update/skipped", "", type=str)

    @skipped_version.setter
    def skipped_version(self, value: str) -> None:
        self._q.setValue("update/skipped", value)

    # --- GitHub ----------------------------------------------------------
    @property
    def github_token(self) -> str:
        return self._secret("github-token", "github/token")

    @github_token.setter
    def github_token(self, value: str) -> None:
        self._set_secret("github-token", "github/token", value)

    # Secrets live in the OS keychain when there is one; the plain QSettings
    # key is the fallback, and the migration path for values saved by versions
    # before 0.42 (moved into the keychain, then erased from the preferences).
    def _secret(self, name: str, legacy_key: str) -> str:
        stored = secrets.get(name)
        if stored:
            self._q.remove(legacy_key)         # belt and braces: no stale copy
            return stored
        legacy = self._q.value(legacy_key, "", type=str)
        if legacy and stored == "" and secrets.set(name, legacy):
            self._q.remove(legacy_key)
        return legacy

    def _set_secret(self, name: str, legacy_key: str, value: str) -> None:
        if secrets.set(name, value):
            self._q.remove(legacy_key)
        elif value:
            self._q.setValue(legacy_key, value)
        else:
            self._q.remove(legacy_key)

    @property
    def github_user(self) -> str:
        return self._q.value("github/user", "", type=str)

    @github_user.setter
    def github_user(self, value: str) -> None:
        self._q.setValue("github/user", value)

    # --- Log panel columns -----------------------------------------------
    def log_columns(self, compact: bool) -> list[int]:
        """Column widths the user dragged in the Log panel, per window mode.

        Empty means "never dragged", so the panel keeps sizing them itself.
        """
        raw = self._q.value(self._log_columns_key(compact), [], type=list) or []
        try:
            return [int(w) for w in raw]
        except (TypeError, ValueError):
            return []

    def set_log_columns(self, compact: bool, widths: list[int]) -> None:
        self._q.setValue(self._log_columns_key(compact),
                         [int(w) for w in widths])

    @staticmethod
    def _log_columns_key(compact: bool) -> str:
        return f"log/columns_{'compact' if compact else 'full'}"

    # --- per-project: interpreter and run configurations -------------------
    @staticmethod
    def _project_key(root: str) -> str:
        """A QSettings-safe key for a project folder ('/' would nest groups)."""
        norm = os.path.normcase(os.path.abspath(root or ""))
        return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]

    def interpreter(self, root: str) -> str:
        """The Python the user picked for *root*, or "" for automatic."""
        return self._q.value(f"project/{self._project_key(root)}/interpreter", "", type=str)

    def set_interpreter(self, root: str, path: str) -> None:
        self._q.setValue(f"project/{self._project_key(root)}/interpreter", path)

    def run_configs(self, root: str) -> list[dict]:
        raw = self._q.value(f"project/{self._project_key(root)}/run_configs", "", type=str)
        try:
            data = json.loads(raw) if raw else []
        except ValueError:
            return []
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []

    def set_run_configs(self, root: str, configs: list[dict]) -> None:
        self._q.setValue(f"project/{self._project_key(root)}/run_configs",
                         json.dumps(configs))

    def selected_run_config(self, root: str) -> str:
        return self._q.value(f"project/{self._project_key(root)}/run_selected", "", type=str)

    def set_selected_run_config(self, root: str, name: str) -> None:
        self._q.setValue(f"project/{self._project_key(root)}/run_selected", name)

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
        return self._secret(f"ai-key-{provider}", f"ai/key/{provider}")

    def set_api_key(self, provider: str, key: str) -> None:
        self._set_secret(f"ai-key-{provider}", f"ai/key/{provider}", key)

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
    # Both keys are versioned together: geometry saved by an older KhervePY
    # holds that version's larger cockpit, and restoring it would silently
    # undo a change to the default size.
    _COMPACT_GEOMETRY_KEY = "window/compact_geometry_v2"

    def save_compact_geometry(self, geometry) -> None:
        self._q.setValue(self._COMPACT_GEOMETRY_KEY, geometry)

    def restore_compact_geometry(self):
        return self._q.value(self._COMPACT_GEOMETRY_KEY)

    # The key is versioned: a layout saved by an older KhervePY pins the docks
    # that version put in the cockpit (Terminal on the left), and restoring it
    # would silently undo the current arrangement. A new key starts clean.
    _COMPACT_STATE_KEY = "window/compact_state_v2"

    def save_compact_state(self, state) -> None:
        self._q.setValue(self._COMPACT_STATE_KEY, state)

    def restore_compact_state(self):
        return self._q.value(self._COMPACT_STATE_KEY)
