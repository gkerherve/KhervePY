"""A PyCharm-style Git branch chip for the toolbar.

Shows the current branch (auto-detected when a local folder is opened) and
drops down to the common VCS actions plus a checkout list of local and remote
branches. The dropdown header reflects the signed-in GitHub account.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMenu, QMessageBox, QToolButton

from khervepy import git_backend as gb
from khervepy import icons


class BranchWidget(QToolButton):
    """Toolbar button whose menu mirrors PyCharm's branch popup."""

    def __init__(self, main_window, color: QColor):
        super().__init__()
        self.mw = main_window
        self._color = color
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setIcon(icons.icon("branch", color))
        self.setAutoRaise(True)

        self._menu = QMenu(self)
        self._menu.aboutToShow.connect(self._rebuild)
        self.setMenu(self._menu)
        self.refresh()

    # --- state -----------------------------------------------------------
    def refresh(self) -> None:
        """Reflect the current project's VCS state on the chip."""
        path = self.mw.project_root
        if gb.is_repo(path):
            branch = gb.current_branch(path) or "(detached)"
            self.setText(f" {branch} ")
            self.setToolTip(f"Git branch: {branch}")
        else:
            self.setText(" No VCS ")
            self.setToolTip("This folder is not a Git repository — click for options")

    # --- menu ------------------------------------------------------------
    def _rebuild(self) -> None:
        m = self._menu
        m.clear()
        path = self.mw.project_root

        # Account header — "knows my account".
        user = self.mw.settings.github_user
        acct = m.addAction(f"  GitHub: {user}" if user else "  GitHub: not signed in")
        acct.setEnabled(False)
        m.addAction("Set token / sign in…", self.mw.set_github_token)
        m.addSeparator()

        if not gb.is_repo(path):
            m.addAction("Clone repository…", self.mw.git_panel.clone_dialog)
            m.addAction("Fork repository…", self.mw.git_panel.fork_dialog)
            m.addAction("Create Git repository here", self._init_repo)
            return

        # Repository / remote header.
        remote = gb.remote_url(path)
        head = m.addAction(f"  {remote}" if remote else "  (no remote)")
        head.setEnabled(False)
        m.addSeparator()

        m.addAction("Update Project (Pull)", self.mw.git_panel._pull)
        m.addAction("Commit…", self._commit)
        m.addAction("Push…", self.mw.git_panel._push)
        m.addAction("Fetch", self._fetch)
        m.addAction("New Branch…", self._new_branch)
        m.addSeparator()

        current = gb.current_branch(path)

        local = m.addAction("Local")
        local.setEnabled(False)
        for b in gb.branches(path):
            act = m.addAction(("  ✔  " if b == current else "      ") + b)
            act.triggered.connect(lambda _=False, br=b: self._checkout(br))

        try:
            remotes = gb.remote_branches(path)
        except gb.GitError:
            remotes = []
        if remotes:
            m.addSeparator()
            rh = m.addAction("Remote")
            rh.setEnabled(False)
            for rb in remotes:
                act = m.addAction("      " + rb)
                act.triggered.connect(lambda _=False, br=rb: self._checkout_remote(br))

    # --- actions ---------------------------------------------------------
    def _after_change(self) -> None:
        self.mw.git_panel.refresh()
        self.refresh()

    def _checkout(self, branch: str) -> None:
        path = self.mw.project_root
        if branch == gb.current_branch(path):
            return
        try:
            gb.checkout(path, branch)
            self.mw._status(f"Switched to {branch}.")
        except gb.GitError as exc:
            QMessageBox.warning(self, "Checkout", str(exc))
        self._after_change()

    def _checkout_remote(self, remote_branch: str) -> None:
        try:
            gb.checkout_track(self.mw.project_root, remote_branch)
            self.mw._status(f"Checked out {remote_branch}.")
        except gb.GitError as exc:
            QMessageBox.warning(self, "Checkout", str(exc))
        self._after_change()

    def _new_branch(self) -> None:
        self.mw.git_panel._new_branch()
        self.refresh()

    def _commit(self) -> None:
        self.mw.git_dock.show()
        self.mw.git_dock.raise_()
        self.mw.git_panel.message.setFocus()

    def _fetch(self) -> None:
        path = self.mw.project_root
        self.mw.git_panel._run_async(
            lambda: gb.fetch(path),
            lambda _: self._after_change(),
            "Fetching",
        )

    def _init_repo(self) -> None:
        try:
            gb.init(self.mw.project_root)
            self.mw._status("Initialised Git repository.")
        except gb.GitError as exc:
            QMessageBox.warning(self, "git init", str(exc))
        self.mw.git_panel.set_repo(self.mw.project_root)
        self.refresh()
