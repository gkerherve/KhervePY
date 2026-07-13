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

from PyQt6.QtGui import QColor, QIcon

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
from khervepy.themes import (
    DEFAULT_THEME,
    THEMES,
    theme_names,
    window_stylesheet,
)


class MainWindow(QMainWindow):
    """Top-level IDE window."""

    def __init__(self, initial_path: str | None = None):
        super().__init__()
        self.settings = Settings()
        self.project_root = os.getcwd()
        self._running = False  # a script is executing under the Run button
        self._killed = False   # the last run was stopped by the user
        self._compact = False  # compact "run & commit" cockpit is active

        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.resize(1200, 780)
        from khervepy.resources import icon_path
        _icon = icon_path()
        if _icon:
            self.setWindowIcon(QIcon(_icon))

        self._build_tabs()
        self._build_docks()
        self._build_toolbar()
        self._build_compact_toolbar()
        self._build_menu()
        self._build_statusbar()
        self._apply_window_theme(self.settings.theme)
        self._restore_window()
        # Safety net: also persist the layout on application quit, in case the
        # window is torn down through a path that skips closeEvent.
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance()
        if _app is not None:
            _app.aboutToQuit.connect(self._save_window)

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
        self._central = container
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
        self.commit_log.show_commit_file.connect(self.show_commit_file_diff)
        log_dock = QDockWidget("Log", self)
        log_dock.setObjectName("log_dock")
        log_dock.setWidget(self.commit_log)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, log_dock)
        self.tabifyDockWidget(git_dock, log_dock)
        log_dock.raise_()
        self.log_dock = log_dock
        # Staging is hidden by default (reopen via View → Git / GitHub).
        git_dock.hide()

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
        self.main_toolbar = tb
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        # Icon-only toolbar; the action text becomes the hover tooltip.
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        tb.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # Icons are drawn in the active theme's foreground colour.
        glyph_color = QColor(THEMES.get(self.settings.theme, THEMES[DEFAULT_THEME]).foreground)
        self._icon_actions: list[tuple] = []  # (action, glyph) for recolouring

        # PyCharm-style Git branch chip, first on the bar.
        self.branch_widget = BranchWidget(self, glyph_color)
        tb.addWidget(self.branch_widget)
        tb.addSeparator()
        # Keep the chip in sync whenever the Git panel refreshes.
        self.git_panel.changed.connect(self.branch_widget.refresh)

        def add(glyph, text, slot, shortcut=None, tip=None):
            act = QAction(icons.icon(glyph, glyph_color), text, self)
            self._icon_actions.append((act, glyph))
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
        self.run_action = add("run", "Run", self.run_current, "F5",
                              "Run the current Python file")
        self.stop_action = add("stop", "Stop", self.stop_run, "Ctrl+F2",
                               "Stop the running program")
        add("debug", "Debug", self.debug_current, "Shift+F5",
            "Debug the current Python file")
        self._update_run_icons()  # paint idle Run/Stop state
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

        # A spacer pins the compact-view toggle to the far right of the bar.
        from PyQt6.QtWidgets import QSizePolicy
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.compact_action = add(
            "compact", "Compact view", self.enter_compact_mode, "Ctrl+Shift+M",
            "Shrink to a Terminal + commit cockpit",
        )

    def _build_compact_toolbar(self) -> None:
        """A minimal toolbar shown only in compact mode: Run, Stop, Maximise."""
        from PyQt6.QtWidgets import QSizePolicy

        ct = QToolBar("Compact")
        ct.setObjectName("compact_toolbar")
        ct.setMovable(False)
        ct.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        ct.setIconSize(QSize(24, 24))
        ct.addWidget(QLabel(" Run & Commit "))
        ct.addAction(self.run_action)
        ct.addAction(self.stop_action)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ct.addWidget(spacer)
        color = QColor(THEMES.get(self.settings.theme, THEMES[DEFAULT_THEME]).foreground)
        self.restore_action = QAction(icons.icon("maximise", color), "Maximise", self)
        self.restore_action.setToolTip("Restore the full editor")
        self.restore_action.triggered.connect(self.exit_compact_mode)
        self._icon_actions.append((self.restore_action, "maximise"))
        ct.addAction(self.restore_action)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, ct)
        ct.hide()
        self.compact_toolbar = ct

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
    # Import name -> pip distribution name, for the common cases where they
    # differ. Anything not listed is installed under its own import name.
    _PIP_NAMES = {
        "cv2": "opencv-python",
        "PIL": "pillow",
        "sklearn": "scikit-learn",
        "yaml": "pyyaml",
        "bs4": "beautifulsoup4",
        "Crypto": "pycryptodome",
        "serial": "pyserial",
        "dotenv": "python-dotenv",
        "dateutil": "python-dateutil",
        "OpenGL": "PyOpenGL",
        "win32api": "pywin32",
        "win32con": "pywin32",
        "win32com": "pywin32",
        "win32gui": "pywin32",
        "wx": "wxPython",
        "docx": "python-docx",
        "pptx": "python-pptx",
        "fitz": "PyMuPDF",
    }

    def run_current(self) -> None:
        editor = self.current_editor()
        if not editor:
            return
        if editor.isModified() or not editor.path:
            self.save_current()
        if not editor.path or not editor.path.endswith(".py"):
            self._status("Run supports .py files.")
            return
        self._run_python_file(editor.path)

    def _run_python_file(self, path: str) -> None:
        import sys
        from PyQt6.QtCore import QProcess

        self.output.clear()
        self.output_dock.show()
        self.output_dock.raise_()
        self._status(f"Running {path}…")
        self._last_run_path = path

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(self.project_root)
        proc.readyReadStandardOutput.connect(
            lambda: self.output.insertPlainText(
                bytes(proc.readAllStandardOutput()).decode(errors="replace")
            )
        )
        proc.finished.connect(self._on_run_finished)
        self._killed = False
        proc.start(sys.executable, [path])
        self._run_proc = proc  # keep a reference
        self._set_running(True)

    def stop_run(self) -> None:
        """Kill the program started by the Run button."""
        from PyQt6.QtCore import QProcess

        proc = getattr(self, "_run_proc", None)
        if proc is not None and proc.state() != QProcess.ProcessState.NotRunning:
            self._killed = True
            proc.kill()
            self._status("Stopping the running program…")
        else:
            self._status("Nothing is running.")

    # Status colours for the Run (running) and Stop (armed) controls.
    _RUN_GREEN = "#3fb950"
    _STOP_RED = "#f85149"

    def _set_running(self, running: bool) -> None:
        self._running = running
        self._update_run_icons()

    def _update_run_icons(self) -> None:
        if not hasattr(self, "run_action"):
            return
        theme = THEMES.get(self.settings.theme, THEMES[DEFAULT_THEME])
        fg = QColor(theme.foreground)
        running = getattr(self, "_running", False)
        # Run turns green while a program is executing.
        self.run_action.setIcon(
            icons.icon("run", QColor(self._RUN_GREEN) if running else fg)
        )
        # Stop is red and clickable while running, muted and disabled otherwise.
        if running:
            stop_color = QColor(self._STOP_RED)
        else:
            stop_color = QColor(fg)
            stop_color.setAlpha(90)
        self.stop_action.setIcon(icons.icon("stop", stop_color))
        self.stop_action.setEnabled(running)

    def _on_run_finished(self, code: int, _status) -> None:
        self._set_running(False)
        if self._killed:
            self._killed = False
            self._status("Program stopped.")
            return
        self._status(f"Process exited ({code}).")
        if code == 0:
            return
        # A crash on a missing import is the most common first-run failure;
        # offer to pip-install it into the interpreter that ran the script.
        import re
        m = re.search(
            r"No module named ['\"]([\w.]+)['\"]", self.output.toPlainText()
        )
        if m:
            self._offer_missing_module(m.group(1))

    def _offer_missing_module(self, module: str) -> None:
        import sys

        top = module.split(".")[0]
        pkg = self._PIP_NAMES.get(top, top)
        note = f"<br><br>(pip package: <b>{pkg}</b>)" if pkg != top else ""
        answer = QMessageBox.question(
            self,
            "Missing module",
            f"The script stopped because <b>{top}</b> is not installed.<br><br>"
            f"Install it with pip into<br><code>{sys.executable}</code>?{note}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._install_module(pkg)

    def _install_module(self, pkg: str) -> None:
        import sys
        from PyQt6.QtCore import QProcess

        self.output_dock.show()
        self.output_dock.raise_()
        self.output.appendPlainText(
            f"\n$ {sys.executable} -m pip install {pkg}\n"
        )
        self._status(f"Installing {pkg}…")

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(self.project_root)
        proc.readyReadStandardOutput.connect(
            lambda: self.output.insertPlainText(
                bytes(proc.readAllStandardOutput()).decode(errors="replace")
            )
        )
        proc.finished.connect(lambda c, _s: self._on_install_finished(c, pkg))
        proc.start(sys.executable, ["-m", "pip", "install", pkg])
        self._pip_proc = proc  # keep a reference

    def _on_install_finished(self, code: int, pkg: str) -> None:
        if code != 0:
            self._status(f"pip install failed (exit {code}).")
            QMessageBox.warning(
                self, "Install failed",
                f"pip could not install {pkg} (exit code {code}).\n"
                "See the Output panel for details.",
            )
            return
        self._status(f"Installed {pkg}.")
        path = getattr(self, "_last_run_path", "")
        if path and os.path.exists(path):
            answer = QMessageBox.question(
                self, "Installed",
                f"<b>{pkg}</b> was installed successfully.<br>"
                "Re-run the script now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._run_python_file(path)

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

    def show_commit_file_diff(self, rev: str, file: str) -> None:
        if not gb.is_repo(self.project_root):
            return
        try:
            text = gb.commit_file_diff(self.project_root, rev, file)
        except gb.GitError as exc:
            text = f"git error: {exc}"
        self.diff_view.show_diff(f"{file}  ·  commit {rev[:8]}", text)
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
        self._apply_window_theme(name)
        self._status(f"Theme: {name}")

    def _apply_window_theme(self, name: str) -> None:
        """Dress the whole window (docks, toolbar, menus) in the theme."""
        theme = THEMES.get(name, THEMES[DEFAULT_THEME])
        self.setStyleSheet(window_stylesheet(theme))
        color = QColor(theme.foreground)
        for act, glyph in getattr(self, "_icon_actions", []):
            act.setIcon(icons.icon(glyph, color))
        if hasattr(self, "branch_widget"):
            self.branch_widget.setIcon(icons.icon("branch", color))
        # Run/Stop carry status colours that must survive a theme recolour.
        self._update_run_icons()

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

    # --- compact "run & commit" cockpit ----------------------------------
    def enter_compact_mode(self) -> None:
        """Collapse to a small window: Terminal left, Log (+ commit msg) right."""
        if self._compact:
            return
        # Remember the full layout so Maximise can restore it verbatim.
        self._full_state = self.saveState()
        self._full_geom = self.saveGeometry()
        self._compact = True

        # Strip the chrome down to the cockpit.
        self.menuBar().hide()
        self.statusBar().hide()
        self.main_toolbar.hide()
        self._central.hide()
        for d in (self.tree_dock, self.search_dock, self.log_dock,
                  self.output_dock, self.terminal_dock, self.debugger_dock,
                  self.diff_dock, self.git_dock):
            d.hide()

        # Left: Terminal.  Right: Log (commit graph + full commit message).
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.terminal_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.log_dock)
        for d in (self.terminal_dock, self.log_dock):
            d.show()
        self.terminal_dock.raise_()

        self.compact_toolbar.show()
        self.resize(1000, 560)

    def exit_compact_mode(self) -> None:
        """Return to the full editor, restoring the pre-compact layout."""
        if not self._compact:
            return
        self._compact = False
        self.compact_toolbar.hide()
        self.menuBar().show()
        self.statusBar().show()
        self.main_toolbar.show()
        self._central.show()
        if getattr(self, "_full_state", None) is not None:
            self.restoreGeometry(self._full_geom)
            self.restoreState(self._full_state)

    # --- window state ----------------------------------------------------
    def _restore_window(self) -> None:
        geo = self.settings.restore_geometry()
        state = self.settings.restore_state()
        if geo is not None:
            self.restoreGeometry(geo)
        if state is not None:
            # restoreState() re-applies each dock/toolbar position, size,
            # tab grouping, floating state and visibility by objectName.
            self.restoreState(state)

    def _save_window(self) -> None:
        """Persist the current dock/toolbar layout and window geometry."""
        self.settings.save_geometry(self.saveGeometry())
        self.settings.save_state(self.saveState())

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
        # Leave compact mode first, so the persisted layout is the full one.
        if self._compact:
            self.exit_compact_mode()
        # Save the layout *before* tearing down child processes, so a slow or
        # failing stop() can never cost the user their window positions.
        self._save_window()
        self.terminal.stop()
        self.debugger.stop()
        for thread in list(self._gh_threads):
            thread.quit()
            thread.wait()
        super().closeEvent(event)
