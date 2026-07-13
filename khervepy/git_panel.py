"""The Git dock: staging, commit, push/pull, branches, clone and fork.

Network operations (clone, fork, push, pull) run on a worker thread so the UI
stays responsive; fast local queries run inline.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from khervepy import git_backend as gb


class _Worker(QObject):
    """Runs a callable off the GUI thread and reports the outcome."""

    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as exc:  # surfaced to the user via failed
            self.failed.emit(str(exc))


class GitPanel(QWidget):
    """Version-control panel bound to a single working directory."""

    repo_cloned = pyqtSignal(str)  # emits the new working-copy path
    status_message = pyqtSignal(str)
    diff_requested = pyqtSignal(str, bool)  # (file, staged)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.repo_path: str | None = None
        self._threads: list[QThread] = []

        self._build_ui()

    # --- UI --------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Branch row.
        branch_row = QHBoxLayout()
        branch_row.addWidget(QLabel("Branch:"))
        self.branch_box = QComboBox()
        self.branch_box.setEditable(False)
        self.branch_box.activated.connect(self._on_branch_change)
        branch_row.addWidget(self.branch_box, 1)
        self.new_branch_btn = QPushButton("New…")
        self.new_branch_btn.clicked.connect(self._new_branch)
        branch_row.addWidget(self.new_branch_btn)
        layout.addLayout(branch_row)

        # Changed-files list.
        layout.addWidget(QLabel("Changes"))
        self.files = QListWidget()
        self.files.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.files.itemDoubleClicked.connect(self._request_diff)
        self.files.setToolTip("Double-click a file to view its diff")
        layout.addWidget(self.files, 1)

        stage_row = QHBoxLayout()
        self.stage_btn = QPushButton("Stage")
        self.stage_btn.clicked.connect(self._stage_selected)
        self.stage_all_btn = QPushButton("Stage All")
        self.stage_all_btn.clicked.connect(self._stage_all)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        stage_row.addWidget(self.stage_btn)
        stage_row.addWidget(self.stage_all_btn)
        stage_row.addWidget(self.refresh_btn)
        layout.addLayout(stage_row)

        # Commit message + button.
        self.message = QPlainTextEdit()
        self.message.setPlaceholderText("Commit message…")
        self.message.setFixedHeight(60)
        layout.addWidget(self.message)

        self.commit_btn = QPushButton("Commit")
        self.commit_btn.clicked.connect(self._commit)
        layout.addWidget(self.commit_btn)

        # Sync row.
        sync_row = QHBoxLayout()
        self.pull_btn = QPushButton("Pull")
        self.pull_btn.clicked.connect(self._pull)
        self.push_btn = QPushButton("Push")
        self.push_btn.clicked.connect(self._push)
        sync_row.addWidget(self.pull_btn)
        sync_row.addWidget(self.push_btn)
        layout.addLayout(sync_row)

        # Remote row.
        remote_row = QHBoxLayout()
        self.clone_btn = QPushButton("Clone…")
        self.clone_btn.clicked.connect(self.clone_dialog)
        self.fork_btn = QPushButton("Fork…")
        self.fork_btn.clicked.connect(self.fork_dialog)
        remote_row.addWidget(self.clone_btn)
        remote_row.addWidget(self.fork_btn)
        layout.addLayout(remote_row)

        self.info = QLabel("No repository.")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self._set_repo_actions_enabled(False)

    def _set_repo_actions_enabled(self, enabled: bool) -> None:
        for w in (
            self.branch_box, self.new_branch_btn, self.files, self.stage_btn,
            self.stage_all_btn, self.refresh_btn, self.message, self.commit_btn,
            self.pull_btn, self.push_btn,
        ):
            w.setEnabled(enabled)

    # --- repository binding ---------------------------------------------
    def set_repo(self, path: str) -> None:
        self.repo_path = path if path and gb.is_repo(path) else None
        self._set_repo_actions_enabled(self.repo_path is not None)
        self.refresh()

    def refresh(self) -> None:
        self.files.clear()
        if not self.repo_path:
            self.info.setText("Not a git repository. Use Clone or open a repo folder.")
            self.branch_box.clear()
            return
        try:
            st = gb.status(self.repo_path)
            self.branch_box.blockSignals(True)
            self.branch_box.clear()
            self.branch_box.addItems(gb.branches(self.repo_path))
            idx = self.branch_box.findText(st.branch)
            if idx >= 0:
                self.branch_box.setCurrentIndex(idx)
            self.branch_box.blockSignals(False)

            for code, name in st.staged:
                self._add_file(f"[staged {code}] {name}", name, staged=True)
            for code, name in st.unstaged:
                self._add_file(f"[{code}] {name}", name, staged=False)
            for name in st.untracked:
                self._add_file(f"[new] {name}", name, staged=False)

            bits = [f"On {st.branch}"]
            if st.ahead:
                bits.append(f"↑{st.ahead}")
            if st.behind:
                bits.append(f"↓{st.behind}")
            if st.is_clean:
                bits.append("· clean")
            self.info.setText("  ".join(bits))
        except gb.GitError as exc:
            self.info.setText(f"git error: {exc}")

    def _add_file(self, label: str, name: str, staged: bool) -> None:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setData(Qt.ItemDataRole.UserRole + 1, staged)
        self.files.addItem(item)

    # --- local actions ---------------------------------------------------
    def _selected_files(self) -> list[str]:
        return [
            it.data(Qt.ItemDataRole.UserRole)
            for it in self.files.selectedItems()
        ]

    def _request_diff(self, item) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        staged = bool(item.data(Qt.ItemDataRole.UserRole + 1))
        if name:
            self.diff_requested.emit(name, staged)

    def _stage_selected(self) -> None:
        files = self._selected_files()
        if not files:
            return
        try:
            gb.stage(self.repo_path, files)
        except gb.GitError as exc:
            self._error(str(exc))
        self.refresh()

    def _stage_all(self) -> None:
        try:
            gb.stage_all(self.repo_path)
        except gb.GitError as exc:
            self._error(str(exc))
        self.refresh()

    def _commit(self) -> None:
        msg = self.message.toPlainText().strip()
        if not msg:
            self._error("Enter a commit message first.")
            return
        try:
            gb.commit(self.repo_path, msg)
            self.message.clear()
            self.status_message.emit("Committed.")
        except gb.GitError as exc:
            self._error(str(exc))
        self.refresh()

    def _on_branch_change(self) -> None:
        branch = self.branch_box.currentText()
        if not branch or branch == gb.current_branch(self.repo_path):
            return
        try:
            gb.checkout(self.repo_path, branch)
            self.status_message.emit(f"Switched to {branch}.")
        except gb.GitError as exc:
            self._error(str(exc))
        self.refresh()

    def _new_branch(self) -> None:
        name, ok = QInputDialog.getText(self, "New branch", "Branch name:")
        if not ok or not name.strip():
            return
        try:
            gb.checkout(self.repo_path, name.strip(), create=True)
            self.status_message.emit(f"Created {name.strip()}.")
        except gb.GitError as exc:
            self._error(str(exc))
        self.refresh()

    # --- network actions -------------------------------------------------
    def _run_async(self, fn, on_done, label: str) -> None:
        self.status_message.emit(f"{label}…")
        thread = QThread(self)
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def cleanup():
            thread.quit()
            thread.wait()
            if thread in self._threads:
                self._threads.remove(thread)

        def handle_done(result):
            on_done(result)
            cleanup()

        def handle_fail(msg):
            self._error(msg)
            cleanup()

        worker.done.connect(handle_done)
        worker.failed.connect(handle_fail)
        self._threads.append(thread)
        thread.start()

    def _pull(self) -> None:
        path = self.repo_path
        self._run_async(
            lambda: gb.pull(path),
            lambda _: (self.status_message.emit("Pulled."), self.refresh()),
            "Pulling",
        )

    def _push(self) -> None:
        path = self.repo_path
        branch = gb.current_branch(path)

        def do_push():
            try:
                return gb.push(path, branch=branch)
            except gb.GitError:
                # No upstream yet — set it.
                return gb.push(path, branch=branch, set_upstream=True)

        self._run_async(
            do_push,
            lambda _: (self.status_message.emit("Pushed."), self.refresh()),
            "Pushing",
        )

    def clone_dialog(self) -> None:
        url, ok = QInputDialog.getText(
            self, "Clone repository", "GitHub/Git URL:"
        )
        if not ok or not url.strip():
            return
        from PyQt6.QtWidgets import QFileDialog

        base = QFileDialog.getExistingDirectory(self, "Clone into folder…")
        if not base:
            return
        url = url.strip()
        name = url.rstrip("/").split("/")[-1].removesuffix(".git")
        dest = os.path.join(base, name)
        token = self.settings.github_token

        self._run_async(
            lambda: gb.clone(url, dest, token),
            lambda _: (
                self.status_message.emit(f"Cloned into {dest}."),
                self.repo_cloned.emit(dest),
            ),
            f"Cloning {name}",
        )

    def fork_dialog(self) -> None:
        token = self.settings.github_token
        if not token:
            self._error(
                "Set a GitHub token first (GitHub → Set Token) to fork repos."
            )
            return
        url, ok = QInputDialog.getText(
            self, "Fork repository", "GitHub repo URL to fork:"
        )
        if not ok or not url.strip():
            return
        url = url.strip()

        def do_fork():
            data = gb.fork_repo(url, token)
            return data.get("clone_url") or data.get("html_url", "")

        def offer_clone(clone_url):
            self.status_message.emit(f"Forked → {clone_url}")
            answer = QMessageBox.question(
                self,
                "Fork created",
                f"Fork created at:\n{clone_url}\n\nClone it now?",
            )
            if answer == QMessageBox.StandardButton.Yes and clone_url:
                from PyQt6.QtWidgets import QFileDialog

                base = QFileDialog.getExistingDirectory(self, "Clone fork into…")
                if base:
                    name = clone_url.rstrip("/").split("/")[-1].removesuffix(".git")
                    dest = os.path.join(base, name)
                    self._run_async(
                        lambda: gb.clone(clone_url, dest, token),
                        lambda _: self.repo_cloned.emit(dest),
                        f"Cloning {name}",
                    )

        self._run_async(do_fork, offer_clone, "Forking")

    # --- helpers ---------------------------------------------------------
    def _error(self, msg: str) -> None:
        QMessageBox.warning(self, "Git", msg)
        self.status_message.emit(msg)
