"""The KhervePY main window: toolbar, tabbed editor and docked panels.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
    QToolBar,
    QWidget,
)

from khervepy import __app_name__, __version__, git_backend as gb
from khervepy.editor import CodeEditor
from khervepy.file_tree import FileTree
from khervepy.git_panel import GitPanel
from khervepy.package_manager import PackageManager
from khervepy.settings import Settings
from khervepy.themes import theme_names


class MainWindow(QMainWindow):
    """Top-level IDE window."""

    def __init__(self, initial_path: str | None = None):
        super().__init__()
        self.settings = Settings()
        self.project_root = os.getcwd()

        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.resize(1200, 780)

        self._build_tabs()
        self._build_docks()
        self._build_toolbar()
        self._build_menu()
        self._build_statusbar()
        self._restore_window()

        # Open whatever we were asked to open, else the last project.
        target = initial_path or self.settings.last_project
        if target and os.path.exists(target):
            self.open_path(target)
        else:
            self.set_project_root(self.project_root)

    # --- construction ----------------------------------------------------
    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

    def _build_docks(self) -> None:
        # Project tree (left).
        self.tree = FileTree()
        self.tree.file_activated.connect(self.open_path)
        tree_dock = QDockWidget("Project", self)
        tree_dock.setObjectName("project_dock")
        tree_dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tree_dock)
        self.tree_dock = tree_dock

        # Git panel (right).
        self.git_panel = GitPanel(self.settings)
        self.git_panel.repo_cloned.connect(self._on_repo_cloned)
        self.git_panel.status_message.connect(self._status)
        git_dock = QDockWidget("Git / GitHub", self)
        git_dock.setObjectName("git_dock")
        git_dock.setWidget(self.git_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, git_dock)
        self.git_dock = git_dock

        # Run output (bottom).
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        out_dock = QDockWidget("Output", self)
        out_dock.setObjectName("output_dock")
        out_dock.setWidget(self.output)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, out_dock)
        self.output_dock = out_dock

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        def add(text, slot, shortcut=None, tip=None):
            act = QAction(text, self)
            act.triggered.connect(slot)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.setToolTip(tip or text)
            tb.addAction(act)
            return act

        add("Open Folder", self.open_folder_dialog, "Ctrl+K")
        add("Open File", self.open_file_dialog, "Ctrl+O")
        add("New", self.new_file, "Ctrl+N")
        add("Save", self.save_current, "Ctrl+S")
        tb.addSeparator()
        add("Run", self.run_current, "F5", "Run the current Python file")
        tb.addSeparator()
        add("Commit+Push", self.quick_commit_push, "Ctrl+Shift+P",
            "Stage all, commit and push in one step")
        add("Clone", self.git_panel.clone_dialog)
        add("Fork", self.git_panel.fork_dialog)
        tb.addSeparator()
        add("Packages", self.open_package_manager, "Ctrl+Shift+I")

        # Theme picker lives on the toolbar for quick switching.
        tb.addSeparator()
        tb.addWidget(QLabel(" Theme: "))
        self.theme_box = QComboBox()
        self.theme_box.addItems(theme_names())
        current = self.settings.theme
        idx = self.theme_box.findText(current)
        if idx >= 0:
            self.theme_box.setCurrentIndex(idx)
        self.theme_box.currentTextChanged.connect(self.change_theme)
        tb.addWidget(self.theme_box)

    def _build_menu(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        file_menu.addAction("Open Folder…", self.open_folder_dialog)
        file_menu.addAction("Open File…", self.open_file_dialog)
        file_menu.addAction("New", self.new_file)
        file_menu.addAction("Save", self.save_current)
        file_menu.addAction("Save As…", self.save_current_as)
        file_menu.addSeparator()
        self.recent_menu = file_menu.addMenu("Recent Projects")
        self._rebuild_recent_menu()
        file_menu.addSeparator()
        file_menu.addAction("Quit", self.close)

        view_menu = bar.addMenu("&View")
        view_menu.addAction(self.tree_dock.toggleViewAction())
        view_menu.addAction(self.git_dock.toggleViewAction())
        view_menu.addAction(self.output_dock.toggleViewAction())

        gh_menu = bar.addMenu("&GitHub")
        gh_menu.addAction("Set Token…", self.set_github_token)
        gh_menu.addAction("Clone…", self.git_panel.clone_dialog)
        gh_menu.addAction("Fork…", self.git_panel.fork_dialog)
        gh_menu.addAction("My Repositories…", self.browse_my_repos)
        gh_menu.addSeparator()
        gh_menu.addAction("Commit + Push", self.quick_commit_push)

        run_menu = bar.addMenu("&Run")
        run_menu.addAction("Run current file", self.run_current)
        run_menu.addAction("Environments & Packages…", self.open_package_manager)

        help_menu = bar.addMenu("&Help")
        help_menu.addAction("About", self.about)

    def _build_statusbar(self) -> None:
        self.statusBar().showMessage(f"{__app_name__} {__version__} — ready")

    # --- project / files -------------------------------------------------
    def set_project_root(self, path: str) -> None:
        self.project_root = path
        self.tree.set_root(path)
        self.git_panel.set_repo(path)
        self.settings.last_project = path
        self.settings.push_recent_project(path)
        self._rebuild_recent_menu()
        self.setWindowTitle(f"{__app_name__} {__version__} — {os.path.basename(path) or path}")

    def open_path(self, path: str) -> None:
        if os.path.isdir(path):
            self.set_project_root(path)
            return
        # Already open? focus it.
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if getattr(w, "path", None) == path:
                self.tabs.setCurrentIndex(i)
                return
        editor = CodeEditor(path, font_size=self.settings.font_size)
        editor.apply_theme(self.settings.theme)
        editor.modificationChanged.connect(self._on_modified)
        index = self.tabs.addTab(editor, editor.display_name)
        self.tabs.setCurrentIndex(index)
        self._status(f"Opened {path}")

    def new_file(self) -> None:
        editor = CodeEditor(None, font_size=self.settings.font_size)
        editor.apply_theme(self.settings.theme)
        editor.modificationChanged.connect(self._on_modified)
        index = self.tabs.addTab(editor, "untitled")
        self.tabs.setCurrentIndex(index)

    def open_folder_dialog(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open folder", self.project_root)
        if path:
            self.set_project_root(path)

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open file", self.project_root)
        if path:
            self.open_path(path)

    def current_editor(self) -> CodeEditor | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, CodeEditor) else None

    def save_current(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        if not editor.path:
            self.save_current_as()
            return
        try:
            editor.save()
            self._refresh_tab_title()
            self.git_panel.refresh()
            self._status(f"Saved {editor.path}")
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))

    def save_current_as(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save as", editor.path or self.project_root
        )
        if not path:
            return
        try:
            editor.save(path)
            editor.set_lexer_for_path(path)
            editor.apply_theme(self.settings.theme)
            self._refresh_tab_title()
            self.git_panel.refresh()
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))

    def _close_tab(self, index: int) -> None:
        w = self.tabs.widget(index)
        if isinstance(w, CodeEditor) and w.isModified():
            answer = QMessageBox.question(
                self, "Unsaved changes",
                f"Save changes to {w.display_name}?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save:
                self.tabs.setCurrentIndex(index)
                self.save_current()
        self.tabs.removeTab(index)

    def _on_tab_changed(self, index: int) -> None:
        editor = self.current_editor()
        if editor:
            lang = os.path.splitext(editor.path or "")[1] or "text"
            self._status(f"{editor.display_name} · {lang}")

    def _on_modified(self, _modified: bool) -> None:
        self._refresh_tab_title()

    def _refresh_tab_title(self) -> None:
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor):
                mark = "● " if w.isModified() else ""
                self.tabs.setTabText(i, mark + w.display_name)

    # --- run -------------------------------------------------------------
    def run_current(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        if editor.isModified() or not editor.path:
            self.save_current()
        if not editor.path or not editor.path.endswith(".py"):
            self._status("Run supports .py files.")
            return

        import sys
        from PyQt6.QtCore import QProcess

        self.output.clear()
        self.output_dock.raise_()
        self._status(f"Running {editor.path}…")

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(self.project_root)
        proc.readyReadStandardOutput.connect(
            lambda: self.output.insertPlainText(
                bytes(proc.readAllStandardOutput()).decode(errors="replace")
            )
        )
        proc.finished.connect(
            lambda code, _s: self._status(f"Process exited ({code}).")
        )
        proc.start(sys.executable, [editor.path])
        self._run_proc = proc  # keep a reference

    # --- github ----------------------------------------------------------
    def set_github_token(self) -> None:
        token, ok = QInputDialog.getText(
            self, "GitHub token",
            "Personal access token (repo scope):",
            echo=QLineEdit.EchoMode.Password,
            text=self.settings.github_token,
        )
        if not ok:
            return
        self.settings.github_token = token.strip()
        if token.strip():
            try:
                user = gb.github_user(token.strip())
                self.settings.github_user = user.get("login", "")
                self._status(f"Authenticated as {user.get('login', '?')}.")
            except gb.GitError as exc:
                QMessageBox.warning(self, "GitHub", str(exc))

    def browse_my_repos(self) -> None:
        token = self.settings.github_token
        if not token:
            QMessageBox.information(self, "GitHub", "Set a token first.")
            return
        try:
            repos = gb.list_user_repos(token)
        except gb.GitError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return
        names = [r.get("full_name", "?") for r in repos]
        choice, ok = QInputDialog.getItem(
            self, "My repositories", "Clone which repository?", names, 0, False
        )
        if not ok or not choice:
            return
        match = next((r for r in repos if r.get("full_name") == choice), None)
        if not match:
            return
        url = match.get("clone_url", "")
        base = QFileDialog.getExistingDirectory(self, "Clone into…", self.project_root)
        if base and url:
            name = choice.split("/")[-1]
            dest = os.path.join(base, name)
            try:
                gb.clone(url, dest, token)
                self._on_repo_cloned(dest)
            except gb.GitError as exc:
                QMessageBox.warning(self, "Clone failed", str(exc))

    def quick_commit_push(self) -> None:
        if not gb.is_repo(self.project_root):
            QMessageBox.information(self, "Git", "Current project is not a git repo.")
            return
        # Save open editors first.
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor) and w.isModified() and w.path:
                w.save()
        msg, ok = QInputDialog.getText(self, "Commit + Push", "Commit message:")
        if not ok or not msg.strip():
            return
        try:
            gb.stage_all(self.project_root)
            gb.commit(self.project_root, msg.strip())
        except gb.GitError as exc:
            QMessageBox.warning(self, "Commit failed", str(exc))
            self.git_panel.refresh()
            return
        # Push via the panel's async machinery.
        self.git_panel._push()
        self.git_panel.refresh()

    def _on_repo_cloned(self, dest: str) -> None:
        self.set_project_root(dest)
        self._status(f"Opened cloned repo: {dest}")

    # --- misc ------------------------------------------------------------
    def open_package_manager(self) -> None:
        dlg = PackageManager(self.project_root, self)
        dlg.exec()

    def change_theme(self, name: str) -> None:
        self.settings.theme = name
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor):
                w.apply_theme(name)
        self._status(f"Theme: {name}")

    def about(self) -> None:
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<b>{__app_name__}</b> {__version__}<br>"
            "A lightweight, GitHub-first Python IDE.<br><br>"
            "Copyright (C) 2026 Gwilherm Kerherve<br>"
            "Licensed under the GNU GPL v3.",
        )

    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        for path in self.settings.recent_projects():
            act = self.recent_menu.addAction(path)
            act.triggered.connect(lambda _=False, p=path: self.set_project_root(p))

    def _status(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 8000)

    # --- window state ----------------------------------------------------
    def _restore_window(self) -> None:
        geo = self.settings.restore_geometry()
        state = self.settings.restore_state()
        if geo is not None:
            self.restoreGeometry(geo)
        if state is not None:
            self.restoreState(state)

    def closeEvent(self, event) -> None:
        # Prompt for any unsaved editors.
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor) and w.isModified():
                self.tabs.setCurrentIndex(i)
                answer = QMessageBox.question(
                    self, "Unsaved changes",
                    f"Save changes to {w.display_name} before quitting?",
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                )
                if answer == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                if answer == QMessageBox.StandardButton.Save and w.path:
                    w.save()
        self.settings.save_geometry(self.saveGeometry())
        self.settings.save_state(self.saveState())
        super().closeEvent(event)
