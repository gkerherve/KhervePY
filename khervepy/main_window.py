"""The KhervePY main window: toolbar, tabbed editor and docked panels.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QSize, QThread
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from PyQt6.QtGui import QIcon, QPalette

from khervepy import __app_name__, __version__, git_backend as gb
from khervepy import icons
from khervepy.editor import CodeEditor
from khervepy.file_tree import FileTree
from khervepy.git_panel import _Worker
from khervepy.github_dialog import TokenDialog
from khervepy.branch_widget import BranchWidget
from khervepy.commit_log import CommitLog
from khervepy.find import FindBar, FindInFilesDialog
from khervepy.search_dock import SearchDock
from khervepy.terminal import Terminal
from khervepy.debugger import Debugger
from khervepy.diff_viewer import DiffViewer
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
        from khervepy.resources import icon_path
        _icon = icon_path()
        if _icon:
            self.setWindowIcon(QIcon(_icon))

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

        # The centre stacks the editor tabs above a hideable find/replace bar.
        self.find_bar = FindBar(self.current_editor)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.find_bar)
        self.setCentralWidget(container)

    def _build_docks(self) -> None:
        # Project tree (left).
        self.tree = FileTree()
        self.tree.file_activated.connect(self.open_path)
        tree_dock = QDockWidget("Project", self)
        tree_dock.setObjectName("project_dock")
        tree_dock.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tree_dock)
        self.tree_dock = tree_dock

        # Global search (left, tabbed behind the project tree).
        self.search = SearchDock()
        self.search.open_location.connect(self.open_at_line)
        search_dock = QDockWidget("Search", self)
        search_dock.setObjectName("search_dock")
        search_dock.setWidget(self.search)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, search_dock)
        self.tabifyDockWidget(tree_dock, search_dock)
        tree_dock.raise_()
        self.search_dock = search_dock

        # Git panel (right).
        self.git_panel = GitPanel(self.settings)
        self.git_panel.repo_cloned.connect(self._on_repo_cloned)
        self.git_panel.status_message.connect(self._status)
        git_dock = QDockWidget("Git / GitHub", self)
        git_dock.setObjectName("git_dock")
        git_dock.setWidget(self.git_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, git_dock)
        self.git_dock = git_dock

        # Commit history / Log (right, tabbed with the Git panel).
        self.commit_log = CommitLog()
        self.commit_log.show_commit.connect(self.show_commit_diff)
        log_dock = QDockWidget("Log", self)
        log_dock.setObjectName("log_dock")
        log_dock.setWidget(self.commit_log)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, log_dock)
        self.tabifyDockWidget(git_dock, log_dock)
        git_dock.raise_()
        self.log_dock = log_dock

        # Run output (bottom).
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        out_dock = QDockWidget("Output", self)
        out_dock.setObjectName("output_dock")
        out_dock.setWidget(self.output)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, out_dock)
        self.output_dock = out_dock

        # Integrated terminal (bottom, tabbed with Output).
        self.terminal = Terminal(self.project_root)
        term_dock = QDockWidget("Terminal", self)
        term_dock.setObjectName("terminal_dock")
        term_dock.setWidget(self.terminal)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, term_dock)
        self.tabifyDockWidget(out_dock, term_dock)
        term_dock.raise_()
        self.terminal_dock = term_dock

        # Debugger (bottom, tabbed with Output/Terminal).
        self.debugger = Debugger(self.current_location, self.project_root)
        dbg_dock = QDockWidget("Debugger", self)
        dbg_dock.setObjectName("debugger_dock")
        dbg_dock.setWidget(self.debugger)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dbg_dock)
        self.tabifyDockWidget(out_dock, dbg_dock)
        out_dock.raise_()
        self.debugger_dock = dbg_dock

        # Diff viewer (bottom, tabbed with Output).
        self.diff_view = DiffViewer()
        diff_dock = QDockWidget("Diff", self)
        diff_dock.setObjectName("diff_dock")
        diff_dock.setWidget(self.diff_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, diff_dock)
        self.tabifyDockWidget(out_dock, diff_dock)
        out_dock.raise_()
        self.diff_dock = diff_dock
        self.git_panel.diff_requested.connect(self.show_git_diff)
        self.git_panel.changed.connect(self.commit_log.refresh)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        # Icon-only toolbar; the action text becomes the hover tooltip.
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        tb.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # Icons are drawn in the toolbar's text colour so they suit the OS theme.
        glyph_color = self.palette().color(QPalette.ColorRole.WindowText)

        # PyCharm-style Git branch chip, first on the bar.
        self.branch_widget = BranchWidget(self, glyph_color)
        tb.addWidget(self.branch_widget)
        tb.addSeparator()
        # Keep the chip in sync whenever the Git panel refreshes.
        self.git_panel.changed.connect(self.branch_widget.refresh)

        def add(glyph, text, slot, shortcut=None, tip=None):
            act = QAction(icons.icon(glyph, glyph_color), text, self)
            act.triggered.connect(slot)
            label = tip or text
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
                label = f"{label}  ({shortcut})"
            act.setToolTip(label)
            tb.addAction(act)
            return act

        add("folder", "Open Folder", self.open_folder_dialog, "Ctrl+K")
        add("file", "Open File", self.open_file_dialog, "Ctrl+O")
        add("new", "New", self.new_file, "Ctrl+N")
        add("save", "Save", self.save_current, "Ctrl+S")
        tb.addSeparator()
        add("run", "Run", self.run_current, "F5", "Run the current Python file")
        add("debug", "Debug", self.debug_current, "Shift+F5",
            "Debug the current Python file")
        add("terminal", "Terminal", self.focus_terminal, "Ctrl+`",
            "Show the integrated terminal")
        tb.addSeparator()
        add("find", "Find", lambda: self.find_bar.open(replace=False), "Ctrl+F")
        add("replace", "Replace", lambda: self.find_bar.open(replace=True), "Ctrl+H")
        add("find_in_files", "Find in Files", self.find_in_files, "Ctrl+Shift+F")
        add("search", "Search", self.focus_search, "Ctrl+Shift+S",
            "Project-wide search dock")
        tb.addSeparator()
        add("commit_push", "Commit+Push", self.quick_commit_push, "Ctrl+Shift+P",
            "Stage all, commit and push in one step")
        add("clone", "Clone", self.git_panel.clone_dialog)
        add("fork", "Fork", self.git_panel.fork_dialog)
        tb.addSeparator()
        add("packages", "Packages", self.open_package_manager, "Ctrl+Shift+I")

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

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addAction("Find…", QKeySequence("Ctrl+F"),
                            lambda: self.find_bar.open(replace=False))
        edit_menu.addAction("Replace…", QKeySequence("Ctrl+H"),
                            lambda: self.find_bar.open(replace=True))
        edit_menu.addAction("Find in Files…", QKeySequence("Ctrl+Shift+F"),
                            self.find_in_files)

        view_menu = bar.addMenu("&View")
        view_menu.addAction(self.tree_dock.toggleViewAction())
        view_menu.addAction(self.search_dock.toggleViewAction())
        view_menu.addAction(self.git_dock.toggleViewAction())
        view_menu.addAction(self.log_dock.toggleViewAction())
        view_menu.addAction(self.output_dock.toggleViewAction())
        view_menu.addAction(self.terminal_dock.toggleViewAction())
        view_menu.addAction(self.debugger_dock.toggleViewAction())
        view_menu.addAction(self.diff_dock.toggleViewAction())

        gh_menu = bar.addMenu("&GitHub")
        gh_menu.addAction("Set Token…", self.set_github_token)
        gh_menu.addAction("Clone…", self.git_panel.clone_dialog)
        gh_menu.addAction("Fork…", self.git_panel.fork_dialog)
        gh_menu.addAction("My Repositories…", self.browse_my_repos)
        gh_menu.addSeparator()
        gh_menu.addAction("Commit + Push", self.quick_commit_push)

        run_menu = bar.addMenu("&Run")
        run_menu.addAction("Run current file", self.run_current)
        run_menu.addAction("Debug current file", self.debug_current)
        run_menu.addAction("Environments & Packages…", self.open_package_manager)

        help_menu = bar.addMenu("&Help")
        help_menu.addAction("About", self.about)

    def _build_statusbar(self) -> None:
        self.statusBar().showMessage(f"{__app_name__} {__version__} — ready")
        # Persistent GitHub sign-in indicator (click to open the token dialog).
        self._gh_threads: list[QThread] = []
        self.gh_indicator = QPushButton()
        self.gh_indicator.setFlat(True)
        self.gh_indicator.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gh_indicator.clicked.connect(self.set_github_token)
        self.statusBar().addPermanentWidget(self.gh_indicator)
        self._update_github_indicator()
        # If a token is stored but the user is unknown, verify quietly.
        if self.settings.github_token and not self.settings.github_user:
            self._verify_github_async(self.settings.github_token)

    def _update_github_indicator(self) -> None:
        user = self.settings.github_user
        if user:
            self.gh_indicator.setText(f"GitHub: {user}")
            self.gh_indicator.setToolTip(f"Signed in as {user} — click to change token")
        elif self.settings.github_token:
            self.gh_indicator.setText("GitHub: token set")
            self.gh_indicator.setToolTip("Token stored but not verified — click to test")
        else:
            self.gh_indicator.setText("GitHub: not signed in")
            self.gh_indicator.setToolTip("Click to set a GitHub token")

    def _verify_github_async(self, token: str) -> None:
        """Confirm a token in the background and refresh the indicator."""
        thread = QThread(self)
        worker = _Worker(lambda: gb.github_user(token))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def cleanup():
            thread.quit()
            thread.wait()
            if thread in self._gh_threads:
                self._gh_threads.remove(thread)

        def done(user):
            self.settings.github_user = user.get("login", "")
            self._update_github_indicator()
            cleanup()

        def fail(_msg):
            cleanup()

        worker.done.connect(done)
        worker.failed.connect(fail)
        self._gh_threads.append(thread)
        thread.start()

    # --- project / files -------------------------------------------------
    def set_project_root(self, path: str) -> None:
        self.project_root = path
        self.tree.set_root(path)
        self.search.set_root(path)
        self.terminal.set_cwd(path)
        self.debugger.set_cwd(path)
        self.git_panel.set_repo(path)
        self.commit_log.set_repo(path)
        self.settings.last_project = path
        self.settings.push_recent_project(path)
        self._rebuild_recent_menu()
        if hasattr(self, "branch_widget"):
            self.branch_widget.refresh()
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

    def open_at_line(self, path: str, line: int) -> None:
        """Open ``path`` (if needed) and scroll to ``line`` (1-based)."""
        self.open_path(path)
        editor = self.current_editor()
        if editor is not None and editor.path == path:
            editor.setCursorPosition(max(0, line - 1), 0)
            editor.ensureLineVisible(max(0, line - 1))
            editor.setFocus()

    def find_in_files(self) -> None:
        dlg = FindInFilesDialog(self.project_root, self)
        dlg.open_location.connect(self.open_at_line)
        dlg.show()

    def focus_search(self) -> None:
        self.search_dock.show()
        self.search_dock.raise_()
        self.search.focus_query()

    def focus_terminal(self) -> None:
        self.terminal_dock.show()
        self.terminal_dock.raise_()
        self.terminal.input.setFocus()

    def current_location(self) -> tuple[str, int]:
        """Return ``(path, 1-based-line)`` for the caret in the current editor."""
        editor = self.current_editor()
        if editor is None or not editor.path:
            return "", 1
        return editor.path, editor.getCursorPosition()[0] + 1

    def debug_current(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        if editor.isModified() or not editor.path:
            self.save_current()
        path, _ = self.current_location()
        if not path or not path.endswith(".py"):
            self._status("Debug supports .py files.")
            return
        self.debugger_dock.show()
        self.debugger_dock.raise_()
        self.debugger.start(path)

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
        dlg = TokenDialog(self.settings, self)
        if dlg.exec() != TokenDialog.DialogCode.Accepted:
            return
        token = dlg.token()
        self.settings.github_token = token
        if not token:
            self.settings.github_user = ""
            self._update_github_indicator()
            self._status("GitHub token cleared.")
            return
        if dlg.verified_login:
            # Already verified by the "Test token" button.
            self.settings.github_user = dlg.verified_login
            self._update_github_indicator()
            self._status(f"GitHub: signed in as {dlg.verified_login}.")
        else:
            # Saved without testing — verify quietly in the background.
            self.settings.github_user = ""
            self._update_github_indicator()
            self._verify_github_async(token)

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

    def show_git_diff(self, file: str, staged: bool) -> None:
        if not gb.is_repo(self.project_root):
            return
        try:
            text = gb.diff_file(self.project_root, file, staged)
        except gb.GitError as exc:
            text = f"git error: {exc}"
        state = "staged" if staged else "working tree"
        self.diff_view.show_diff(f"{file}  ·  {state}", text)
        self.diff_dock.show()
        self.diff_dock.raise_()

    def show_commit_diff(self, rev: str) -> None:
        if not gb.is_repo(self.project_root):
            return
        try:
            text = gb.show_commit(self.project_root, rev)
        except gb.GitError as exc:
            text = f"git error: {exc}"
        self.diff_view.show_diff(f"commit {rev}", text)
        self.diff_dock.show()
        self.diff_dock.raise_()

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
        self.terminal.stop()
        self.debugger.stop()
        for thread in list(self._gh_threads):
            thread.quit()
            thread.wait()
        self.settings.save_geometry(self.saveGeometry())
        self.settings.save_state(self.saveState())
        super().closeEvent(event)
