"""The KhervePY main window: toolbar, tabbed editor and docked panels.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QSize, QThread, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
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
from khervepy.ai_chat import AIChat
from khervepy.settings import Settings
from khervepy.themes import (
    DEFAULT_THEME,
    THEMES,
    theme_names,
    window_stylesheet,
)


def _decode(data) -> str:
    """Decode a chunk of child-process output for the Output panel."""
    return bytes(data).decode("utf-8", errors="replace")


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
            _app.aboutToQuit.connect(self._save_open_files)

        # Open whatever we were asked to open, else the last project.
        target = initial_path or self.settings.last_project
        if target and os.path.exists(target):
            self.open_path(target)
        else:
            self.set_project_root(self.project_root)
        # Reopen the editor tabs from the previous session.
        self._restore_open_files()
        self._setup_vcs()
        # Look for a new release once the window is up, so a slow or dead
        # network never delays the editor appearing.
        QTimer.singleShot(3000, self._auto_check_updates)

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
        self.tree.changed.connect(self._schedule_vcs_refresh)
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

        # AI assistant (bottom, tabbed alongside the Terminal).
        self.ai_chat = AIChat(self.settings, self._editor_context, host=self)
        self.ai_chat.status_message.connect(self._status)
        ai_dock = QDockWidget("AI Chat", self)
        ai_dock.setObjectName("ai_dock")
        ai_dock.setWidget(self.ai_chat)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, ai_dock)
        self.tabifyDockWidget(term_dock, ai_dock)
        self.ai_dock = ai_dock

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
        """The cockpit's own toolbar: Open, New Instance, Run, Stop, Maximise.

        Open and New Instance are here because the cockpit has no menu bar and
        no file tree: without them, switching project means restoring the full
        window first.
        """
        from PyQt6.QtWidgets import QSizePolicy

        ct = QToolBar("Compact")
        ct.setObjectName("compact_toolbar")
        ct.setMovable(False)
        ct.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        # Deliberately smaller than the main toolbar: every pixel of chrome is
        # one the cockpit's two panels do not get.
        ct.setIconSize(QSize(18, 18))
        ct.setContentsMargins(0, 0, 0, 0)
        color = QColor(THEMES.get(self.settings.theme, THEMES[DEFAULT_THEME]).foreground)

        def add(glyph, text, slot, tip):
            act = QAction(icons.icon(glyph, color), text, self)
            act.setToolTip(tip)
            act.triggered.connect(slot)
            self._icon_actions.append((act, glyph))
            ct.addAction(act)
            return act

        add("open_folder", "Open Folder", self.open_folder_dialog,
            "Open a project folder  (Ctrl+K)")
        add("new_instance", "New Instance", self.new_instance,
            "Launch a second KhervePY window")
        ct.addSeparator()
        ct.addAction(self.run_action)
        ct.addAction(self.stop_action)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ct.addWidget(spacer)
        self.restore_action = add(
            "maximise", "Maximise", self.exit_compact_mode,
            "Restore the full editor",
        )
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, ct)
        ct.hide()
        self.compact_toolbar = ct

    def _build_menu(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        file_menu.addAction("New Instance", self.new_instance)
        file_menu.addSeparator()
        file_menu.addAction("Open Folder…", self.open_folder_dialog)
        file_menu.addAction("Open File…", self.open_file_dialog)
        file_menu.addAction("New", self.new_file)
        file_menu.addAction("New Python File…", self.new_python_file)
        file_menu.addAction("Save", self.save_current)
        file_menu.addAction("Save As…", self.save_current_as)
        file_menu.addSeparator()
        file_menu.addAction("Open File Location", self.open_file_location)
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

        code_menu = bar.addMenu("&Code")
        code_menu.addAction("Comment with Line Comment", QKeySequence("Ctrl+/"),
                            lambda: self._code_action("toggle_line_comment"))
        code_menu.addAction("Comment with Block Comment",
                            QKeySequence("Ctrl+Shift+/"),
                            lambda: self._code_action("toggle_block_comment"))
        code_menu.addSeparator()
        code_menu.addAction("Duplicate Line/Selection", QKeySequence("Ctrl+D"),
                            lambda: self._code_action("duplicate_line"))
        code_menu.addAction("Delete Line", QKeySequence("Ctrl+Shift+K"),
                            lambda: self._code_action("delete_line"))
        code_menu.addAction("Move Line Up", QKeySequence("Alt+Shift+Up"),
                            lambda: self._code_action("move_line_up"))
        code_menu.addAction("Move Line Down", QKeySequence("Alt+Shift+Down"),
                            lambda: self._code_action("move_line_down"))
        code_menu.addSeparator()
        code_menu.addAction("Collapse/Expand", QKeySequence("Ctrl+."),
                            lambda: self._code_action("toggle_fold"))
        code_menu.addAction("Collapse All", QKeySequence("Ctrl+Shift+-"),
                            lambda: self._code_action("fold_all"))
        code_menu.addAction("Expand All", QKeySequence("Ctrl+Shift+="),
                            lambda: self._code_action("unfold_all"))
        code_menu.addSeparator()
        code_menu.addAction("Go to Line…", QKeySequence("Ctrl+G"),
                            self._go_to_line)

        view_menu = bar.addMenu("&View")
        view_menu.addAction(self.tree_dock.toggleViewAction())
        view_menu.addAction(self.search_dock.toggleViewAction())
        view_menu.addAction(self.git_dock.toggleViewAction())
        view_menu.addAction(self.log_dock.toggleViewAction())
        view_menu.addAction(self.output_dock.toggleViewAction())
        view_menu.addAction(self.terminal_dock.toggleViewAction())
        view_menu.addAction(self.ai_dock.toggleViewAction())
        view_menu.addSeparator()
        self.menubar_action = QAction("Menu Bar", self, checkable=True)
        self.menubar_action.setChecked(True)
        self.menubar_action.setShortcut(QKeySequence("Ctrl+M"))
        self.menubar_action.setToolTip("Show/hide the menu bar (Ctrl+M)")
        self.menubar_action.toggled.connect(self._toggle_menubar)
        view_menu.addAction(self.menubar_action)
        # Also a window-level action so Ctrl+M works while the bar is hidden.
        self.addAction(self.menubar_action)
        # Apply the saved preference.
        self.menubar_action.setChecked(self.settings.menubar_visible)
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
        run_menu.addAction("Check requirements.txt…", self.check_requirements)

        run_menu.addAction("AI Assistant", self.focus_ai_chat)

        help_menu = bar.addMenu("&Help")
        help_menu.addAction("AI Assistant", self.focus_ai_chat)
        help_menu.addAction("Get an API key…", lambda: self.ai_chat.show_help())
        help_menu.addAction("AI API Keys…", lambda: self.ai_chat.open_keys())
        help_menu.addSeparator()
        help_menu.addAction("Check for updates…", self.check_for_updates)
        auto = help_menu.addAction("Check for updates on start-up")
        auto.setCheckable(True)
        auto.setChecked(self.settings.check_updates)
        auto.toggled.connect(self._set_auto_update_check)
        help_menu.addSeparator()
        help_menu.addAction("About KhervePY", self.about)

    def _toggle_menubar(self, visible: bool) -> None:
        self.menuBar().setVisible(visible)
        self.settings.menubar_visible = visible
        if not visible:
            self._status("Menu bar hidden — press Ctrl+M to show it again.")

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
        switching = os.path.abspath(path) != os.path.abspath(self.project_root)
        self.project_root = path
        # When moving to a different project, close editors that don't belong
        # to it (leaving untitled buffers untouched).
        if switching:
            self._close_tabs_outside_project()
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
        self._schedule_vcs_refresh()
        self.setWindowTitle(f"{__app_name__} {__version__} — {os.path.basename(path) or path}")
        self._auto_check_requirements()

    def _is_in_project(self, path: str) -> bool:
        """True if ``path`` lives inside the current project root."""
        if not path:
            return False
        root = os.path.normcase(os.path.abspath(self.project_root))
        p = os.path.normcase(os.path.abspath(path))
        return p == root or p.startswith(root + os.sep)

    def _close_tabs_outside_project(self) -> None:
        """Close file tabs whose path is not inside the current project root."""
        for i in range(self.tabs.count() - 1, -1, -1):
            w = self.tabs.widget(i)
            if not isinstance(w, CodeEditor) or not w.path:
                continue  # keep untitled buffers
            if not self._is_in_project(w.path):
                if w.isModified():  # auto-save is on — flush before closing
                    try:
                        w.save()
                    except OSError:
                        pass
                self.tabs.removeTab(i)
                w.deleteLater()

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
        editor.textChanged.connect(lambda e=editor: self._autosave(e))
        editor.textChanged.connect(self._schedule_vcs_refresh)
        index = self.tabs.addTab(editor, editor.display_name)
        self.tabs.setCurrentIndex(index)
        self._update_change_markers(editor)
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
        self.terminal.view.setFocus()

    def focus_ai_chat(self) -> None:
        self.ai_dock.show()
        self.ai_dock.raise_()
        self.ai_chat.input.setFocus()

    def _editor_context(self):
        """Return ``(filename, text)`` of the current editor for the AI chat."""
        editor = self.current_editor()
        if editor is None:
            return None
        return (os.path.basename(editor.path) if editor.path else "untitled",
                editor.text())

    # --- AI agent host interface -----------------------------------------
    def ai_open_files(self) -> dict:
        """Map absolute path -> current (possibly unsaved) text for open tabs."""
        files = {}
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor) and w.path:
                files[os.path.abspath(w.path)] = w.text()
        return files

    def ai_active_file(self):
        editor = self.current_editor()
        return os.path.abspath(editor.path) if editor and editor.path else None

    def ai_after_agent(self, changed_paths: set, committed: bool) -> None:
        """Reload any open editors the agent wrote, then refresh git views."""
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if not (isinstance(w, CodeEditor) and w.path):
                continue
            if os.path.abspath(w.path) in changed_paths:
                try:
                    w.reload_from_disk()
                except OSError:
                    pass
        if changed_paths or committed:
            self.git_panel.refresh()
            self.commit_log.refresh()
            self._schedule_vcs_refresh()
        if committed:
            self._status("AI agent committed changes.")
        elif changed_paths:
            self._status(f"AI agent edited {len(changed_paths)} file(s).")

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
        editor.textChanged.connect(lambda e=editor: self._autosave(e))
        editor.textChanged.connect(self._schedule_vcs_refresh)
        index = self.tabs.addTab(editor, "untitled")
        self.tabs.setCurrentIndex(index)

    def new_python_file(self) -> None:
        """Create a new empty ``.py`` file on disk and open it in a tab."""
        path, _ = QFileDialog.getSaveFileName(
            self, "New Python file",
            os.path.join(self.project_root or "", "untitled.py"),
            "Python files (*.py)",
        )
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".py"
        try:
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write("")
        except OSError as exc:
            QMessageBox.warning(self, "New file failed", str(exc))
            return
        self.open_path(path)

    def new_instance(self) -> None:
        """Launch a separate KhervePY process."""
        from PyQt6.QtCore import QProcess

        import sys

        if getattr(sys, "frozen", False):
            # Packaged executable: re-run it with the same arguments.
            QProcess.startDetached(sys.executable, sys.argv[1:])
        else:
            QProcess.startDetached(sys.executable, ["-m", "khervepy"])

    def open_file_location(self) -> None:
        """Reveal the current file (or project root) in the OS file browser."""
        import subprocess
        import sys

        editor = self.current_editor()
        target = editor.path if editor and editor.path else self.project_root
        if not target or not os.path.exists(target):
            self._status("No file location to open.")
            return
        target = os.path.abspath(target)
        try:
            if sys.platform.startswith("win"):
                if os.path.isdir(target):
                    os.startfile(target)  # type: ignore[attr-defined]
                else:
                    subprocess.run(["explorer", "/select,", target])
            elif sys.platform == "darwin":
                if os.path.isdir(target):
                    subprocess.run(["open", target])
                else:
                    subprocess.run(["open", "-R", target])
            else:
                folder = target if os.path.isdir(target) else os.path.dirname(target)
                subprocess.run(["xdg-open", folder])
        except OSError as exc:
            QMessageBox.warning(self, "Open location failed", str(exc))

    def project_entry_point(self, root: str) -> str:
        """Return the project's obvious script to run, or "".

        Two conventions cover almost every project: ``main.py``, and a script
        named after the folder itself (``KherveStats/KherveStats.py``). Only
        the project root is looked at — a ``main.py`` buried three packages
        deep is not what someone means by "run this project".
        """
        root = os.path.abspath(root)
        names = ("main.py", os.path.basename(os.path.normpath(root)) + ".py")
        for name in names:
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate):
                return candidate
        return ""

    def open_folder_dialog(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open folder", self.project_root)
        if not path:
            return
        self.set_project_root(path)
        # Open the entry point so Run works straight away — in the cockpit
        # especially, where there is no file tree to pick a script from.
        entry = self.project_entry_point(path)
        if entry:
            self.open_path(entry)
            note = f"Opened {os.path.basename(entry)} — press F5 to run."
        else:
            note = (f"Opened {os.path.basename(os.path.normpath(path))} — no "
                    "main.py found; open a file to run.")
        self._status(note)
        if self._compact:
            # The cockpit hides the status bar, so say it where it can be seen.
            self.output.clear()
            self._output_append(f"[KhervePY] {note}\n")

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open file", self.project_root)
        if path:
            self.open_path(path)

    def current_editor(self) -> CodeEditor | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, CodeEditor) else None

    # --- Code menu -------------------------------------------------------
    def _code_action(self, method: str) -> None:
        """Dispatch a Code-menu command to the focused editor."""
        editor = self.current_editor()
        if editor is not None:
            getattr(editor, method)()

    def _go_to_line(self) -> None:
        editor = self.current_editor()
        if editor is None:
            return
        current = editor.getCursorPosition()[0] + 1
        n, ok = QInputDialog.getInt(
            self, "Go to line", "Line:", current, 1, max(1, editor.lines())
        )
        if ok:
            editor.setCursorPosition(n - 1, 0)
            editor.ensureLineVisible(n - 1)
            editor.setFocus()

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
            if w.path:
                # Auto-save is on for path-backed files: just flush it silently.
                try:
                    w.save()
                except OSError:
                    pass
            else:
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
            self._update_change_markers(editor)

    def _on_modified(self, _modified: bool) -> None:
        self._refresh_tab_title()

    # --- auto-save -------------------------------------------------------
    def _autosave(self, editor: CodeEditor) -> None:
        """Schedule a near-immediate save after an edit (debounced per editor)."""
        if not getattr(editor, "path", None):
            return  # untitled buffers have nowhere to save yet
        timer = getattr(editor, "_autosave_timer", None)
        if timer is None:
            from PyQt6.QtCore import QTimer
            timer = QTimer(editor)
            timer.setSingleShot(True)
            timer.setInterval(250)
            timer.timeout.connect(lambda e=editor: self._do_autosave(e))
            editor._autosave_timer = timer
        timer.start()  # restart the debounce window on every keystroke

    def _do_autosave(self, editor: CodeEditor) -> None:
        if editor.path and editor.isModified():
            try:
                editor.save()
                self._refresh_tab_title()
                self._schedule_vcs_refresh()
            except OSError as exc:
                self._status(f"Auto-save failed: {exc}")

    # --- version-control decorations -------------------------------------
    def _setup_vcs(self) -> None:
        """Debounced refresh of tree colours + editor change bars."""
        from PyQt6.QtCore import QTimer
        self._vcs_timer = QTimer(self)
        self._vcs_timer.setSingleShot(True)
        self._vcs_timer.setInterval(350)
        self._vcs_timer.timeout.connect(self._do_vcs_refresh)
        self.git_panel.changed.connect(self._schedule_vcs_refresh)
        self._schedule_vcs_refresh()

    def _schedule_vcs_refresh(self) -> None:
        timer = getattr(self, "_vcs_timer", None)
        if timer is not None:
            timer.start()

    def _do_vcs_refresh(self) -> None:
        root = self.project_root
        in_repo = gb.is_repo(root)
        self.tree.set_status_map(gb.status_map(root) if in_repo else {})
        self._update_change_markers(self.current_editor())

    def _update_change_markers(self, editor: CodeEditor | None) -> None:
        """Diff the current buffer against HEAD and paint the change bar."""
        if editor is None or not getattr(editor, "path", None):
            return
        root = self.project_root
        if not gb.is_repo(root):
            editor.set_change_markers([], [], [])
            return
        rel = os.path.relpath(editor.path, root).replace(os.sep, "/")
        if rel.startswith(".."):
            editor.set_change_markers([], [], [])
            return
        head = gb.file_at_head(root, rel)
        if head is None:  # new/untracked file — every line is an addition
            editor.set_change_markers(list(range(editor.lines())), [], [])
            return
        import difflib
        a = head.splitlines()
        b = editor.text().splitlines()
        added: list[int] = []
        modified: list[int] = []
        deleted: list[int] = []
        for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(
                None, a, b, autojunk=False).get_opcodes():
            if tag == "insert":
                added.extend(range(j1, j2))
            elif tag == "replace":
                modified.extend(range(j1, j2))
            elif tag == "delete":
                deleted.append(j1)
        editor.set_change_markers(added, modified, deleted)

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

    # --- Output panel plumbing -------------------------------------------
    # Reds that stay legible against a dark and a light editor background.
    _ERROR_DARK = "#ff6b6b"
    _ERROR_LIGHT = "#c62828"

    def _output_colour(self, error: bool) -> QColor:
        """The pen for normal output, or the red for anything from stderr."""
        theme = THEMES.get(self.settings.theme, THEMES[DEFAULT_THEME])
        if not error:
            return QColor(theme.foreground)
        background = QColor(theme.background)
        # Relative luminance decides which red keeps its contrast.
        light = (0.299 * background.red() + 0.587 * background.green()
                 + 0.114 * background.blue()) > 140
        return QColor(self._ERROR_LIGHT if light else self._ERROR_DARK)

    def _output_append(self, text: str, error: bool = False) -> None:
        """Append to the Output panel, always at the end and always visible.

        ``insertPlainText`` writes at the caret, so a click anywhere in the
        panel would scatter later output around it; append explicitly instead.
        Anything the child wrote to stderr — tracebacks, warnings — goes in red.
        """
        if not text:
            return
        from PyQt6.QtGui import QTextCursor, QTextCharFormat

        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        char_format = QTextCharFormat()
        char_format.setForeground(self._output_colour(error))
        cursor.insertText(text, char_format)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _stream_output(self, proc) -> None:
        """Stream both channels of *proc* into the Output panel.

        The channels are kept apart so stderr can be coloured. The cost is that
        stdout and stderr no longer interleave in the exact order the program
        wrote them — the same trade every IDE that colours errors makes, and
        worth it to see a traceback at a glance.
        """
        proc.readyReadStandardOutput.connect(
            lambda: self._output_append(_decode(proc.readAllStandardOutput()))
        )
        proc.readyReadStandardError.connect(
            lambda: self._output_append(_decode(proc.readAllStandardError()),
                                        error=True)
        )

    def _drain_output(self, proc) -> None:
        """Read whatever the child left in the pipes when it exited.

        A program that dies quickly — an ImportError on line 1 — can exit
        before Qt delivers the last ``readyRead``, so the traceback would
        otherwise never reach the panel.
        """
        self._output_append(_decode(proc.readAllStandardOutput()))
        self._output_append(_decode(proc.readAllStandardError()), error=True)

    def run_current(self) -> None:
        editor = self.current_editor()
        if not editor:
            self._status("Nothing to run — open a Python file first.")
            return
        if editor.isModified() or not editor.path:
            self.save_current()
        if not editor.path or not editor.path.endswith(".py"):
            self._status("Run supports .py files.")
            return
        self._run_python_file(editor.path)

    def _run_python_file(self, path: str) -> None:
        from PyQt6.QtCore import QProcess, QProcessEnvironment
        from khervepy.proc import hide_console, python_executable

        python = python_executable(self.project_root)
        if not python:
            self._no_python_message()
            return

        self.output.clear()
        self.output_dock.show()
        self.output_dock.raise_()
        self._status(f"Running {path}…")
        self._last_run_path = path
        self._run_python = python  # interpreter this run used (for auto-install)

        proc = QProcess(self)
        hide_console(proc)
        # Separate channels so stderr can be told apart and shown in red.
        proc.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels)
        cwd = self.project_root or os.path.dirname(path)
        proc.setWorkingDirectory(cwd)
        # Force unbuffered stdout/stderr so the program's prints stream into the
        # Output panel live; a pipe (not a console) otherwise block-buffers them,
        # leaving Output empty until the process exits. UTF-8 keeps tracebacks
        # with accents or arrows readable instead of mojibake.
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        proc.setProcessEnvironment(env)
        # Echo the command first: which interpreter and which directory a run
        # used is the single most useful clue when it behaves differently from
        # a terminal, and it costs one line.
        self._output_append(f'"{python}" -u "{path}"\n[cwd: {cwd}]\n\n')
        self._stream_output(proc)
        proc.errorOccurred.connect(lambda err: self._on_run_error(err, python))
        proc.finished.connect(self._on_run_finished)
        self._killed = False
        self._run_proc = proc  # keep a reference
        # Arm the Run/Stop icons *before* starting: a failure to start emits
        # errorOccurred synchronously from start(), and arming afterwards would
        # overwrite the idle state that handler just restored.
        self._set_running(True)
        proc.start(python, ["-u", path])

    def _on_run_error(self, err, python: str) -> None:
        """Report a QProcess-level failure in the Output panel.

        Without this a start failure is completely invisible: the child never
        writes a byte and ``finished`` is never emitted, so Output stays empty
        and the Run button stays green for ever.
        """
        from PyQt6.QtCore import QProcess
        from khervepy.proc import is_store_stub

        if self._killed and err == QProcess.ProcessError.Crashed:
            return  # our own Stop button; reported by _on_run_finished
        hint = ""
        if is_store_stub(python):
            # A 0-byte WindowsApps alias: Python was never installed from the
            # Store, so the stub only knows how to open the Store page.
            hint = ("\nThat path is a Microsoft Store placeholder, not a real "
                    "Python.\nInstall Python from python.org, or turn off the "
                    "'python' app\nexecution alias in Settings › Apps › "
                    "Advanced app settings.")
        reasons = {
            QProcess.ProcessError.FailedToStart:
                f"could not start the interpreter\n  {python}\n"
                f"in the working directory\n  {self.project_root}" + hint,
            QProcess.ProcessError.Crashed: "the program crashed.",
            QProcess.ProcessError.Timedout: "the process timed out.",
            QProcess.ProcessError.WriteError: "could not write to the process.",
            QProcess.ProcessError.ReadError:
                "could not read the process output.",
        }
        reason = reasons.get(err, "the process failed for an unknown reason.")
        self._output_append(f"\n[KhervePY] Run failed — {reason}\n", error=True)
        self._status("Run failed — see the Output panel.")
        if err == QProcess.ProcessError.FailedToStart:
            self._set_running(False)  # `finished` will never arrive

    def _no_python_message(self) -> None:
        QMessageBox.warning(
            self, "No Python found",
            "KhervePY couldn't find a Python interpreter to run the script.\n\n"
            "Install Python (and put it on PATH), or create a virtual "
            "environment in the project via Packages (Ctrl+Shift+I).",
        )
        self._status("No Python interpreter found.")

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

    def _on_run_finished(self, code: int, status) -> None:
        from PyQt6.QtCore import QProcess

        proc = getattr(self, "_run_proc", None)
        if proc is not None:
            self._drain_output(proc)  # last bytes of a fast-failing program
        self._set_running(False)
        if self._killed:
            self._killed = False
            self._output_append("\n[Process stopped]\n")
            self._status("Program stopped.")
            return
        if status == QProcess.ExitStatus.CrashExit:
            self._output_append("\n[Process crashed]\n", error=True)
            self._status("Process crashed.")
        else:
            self._output_append(
                f"\n[Process finished with exit code {code}]\n",
                error=code != 0)
            self._status(f"Process exited ({code}).")
        if code == 0 and status == QProcess.ExitStatus.NormalExit:
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
        top = module.split(".")[0]
        pkg = self._PIP_NAMES.get(top, top)
        python = getattr(self, "_run_python", "") or "the current interpreter"
        note = f"<br><br>(pip package: <b>{pkg}</b>)" if pkg != top else ""
        answer = QMessageBox.question(
            self,
            "Missing module",
            f"The script stopped because <b>{top}</b> is not installed.<br><br>"
            f"Install it with pip into<br><code>{python}</code>?{note}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._install_module(pkg)

    def _install_module(self, pkg: str) -> None:
        from PyQt6.QtCore import QProcess
        from khervepy.proc import hide_console, python_executable

        python = getattr(self, "_run_python", "") or python_executable(self.project_root)
        if not python:
            self._no_python_message()
            return
        self.output_dock.show()
        self.output_dock.raise_()
        self._output_append(f'\n$ "{python}" -m pip install {pkg}\n')
        self._status(f"Installing {pkg}…")

        proc = QProcess(self)
        hide_console(proc)
        # Separate channels so stderr can be told apart and shown in red.
        proc.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels)
        proc.setWorkingDirectory(self.project_root)
        self._stream_output(proc)
        proc.errorOccurred.connect(
            lambda _e: self._output_append(
                f"\n[KhervePY] pip could not be started with\n  {python}\n",
                error=True,
            )
        )
        proc.finished.connect(lambda c, _s: self._on_install_finished(c, pkg))
        proc.start(python, ["-m", "pip", "install", pkg])
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

    # --- requirements ----------------------------------------------------
    def check_requirements(self) -> None:
        """Compare the project's requirements.txt against the interpreter and
        report which packages are missing, offering to install them."""
        from PyQt6.QtWidgets import QApplication
        from khervepy import requirements as reqmod
        from khervepy.proc import python_executable

        path = reqmod.find_requirements_file(self.project_root)
        if not path:
            QMessageBox.information(
                self, "No requirements.txt",
                "This project has no requirements.txt in its root folder.",
            )
            return
        python = python_executable(self.project_root)
        if not python:
            self._no_python_message()
            return

        self._status("Checking requirements…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        thread = QThread(self)
        worker = _Worker(lambda: reqmod.check_requirements(path, python))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def cleanup():
            QApplication.restoreOverrideCursor()
            thread.quit()
            thread.wait()
            if thread in self._gh_threads:
                self._gh_threads.remove(thread)

        def done(result):
            cleanup()
            self._show_requirements_result(result)

        def fail(msg):
            cleanup()
            self._status("Requirements check failed.")
            QMessageBox.warning(self, "Requirements check failed", msg)

        worker.done.connect(done)
        worker.failed.connect(fail)
        self._gh_threads.append(thread)
        thread.start()

    def _show_requirements_result(self, result) -> None:
        total = len(result.requirements)
        missing = result.missing
        if not total:
            self._status("requirements.txt lists no packages.")
            QMessageBox.information(
                self, "Requirements", "requirements.txt lists no packages.",
            )
            return
        if not missing:
            self._status(f"All {total} requirements are installed.")
            QMessageBox.information(
                self, "Requirements",
                f"All {total} requirement(s) are installed. ✔",
            )
            return

        names = "<br>".join(f"• <b>{r.name}</b>{r.specifier}" for r in missing)
        self._status(f"{len(missing)} of {total} requirements missing.")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Missing requirements")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(
            f"{len(missing)} of {total} requirement(s) are not installed in "
            "the interpreter:<br><br>" + names
        )
        install_btn = box.addButton("Install missing", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is install_btn:
            self._pip_install_specs([r.raw for r in missing])

    def _pip_install_specs(self, specs: list[str]) -> None:
        """pip-install the given requirement specifiers into the interpreter,
        streaming progress into the Output panel."""
        from PyQt6.QtCore import QProcess
        from khervepy.proc import hide_console, python_executable

        if not specs:
            return
        python = python_executable(self.project_root)
        if not python:
            self._no_python_message()
            return
        self.output_dock.show()
        self.output_dock.raise_()
        self._output_append(
            f"\n$ \"{python}\" -m pip install {' '.join(specs)}\n"
        )
        self._status("Installing missing requirements…")

        proc = QProcess(self)
        hide_console(proc)
        # Separate channels so stderr can be told apart and shown in red.
        proc.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels)
        proc.setWorkingDirectory(self.project_root)
        self._stream_output(proc)
        proc.errorOccurred.connect(
            lambda _e: self._output_append(
                f"\n[KhervePY] pip could not be started with\n  {python}\n",
                error=True,
            )
        )
        proc.finished.connect(lambda c, _s: self._on_requirements_installed(c))
        proc.start(python, ["-m", "pip", "install", *specs])
        self._pip_proc = proc  # keep a reference

    def _on_requirements_installed(self, code: int) -> None:
        if code != 0:
            self._status(f"pip install failed (exit {code}).")
            QMessageBox.warning(
                self, "Install failed",
                f"pip could not install the missing requirements (exit {code}).\n"
                "See the Output panel for details.",
            )
            return
        self._status("Missing requirements installed.")

    def _auto_check_requirements(self) -> None:
        """On opening a project, quietly flag missing requirements in the status
        bar (no modal) so a silent gap like a missing icon font is visible."""
        from khervepy import requirements as reqmod
        from khervepy.proc import python_executable

        path = reqmod.find_requirements_file(self.project_root)
        if not path:
            return
        python = python_executable(self.project_root)
        if not python:
            return
        thread = QThread(self)
        worker = _Worker(lambda: reqmod.check_requirements(path, python))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def cleanup():
            thread.quit()
            thread.wait()
            if thread in self._gh_threads:
                self._gh_threads.remove(thread)

        def done(result):
            if result.missing:
                self._status(
                    f"{len(result.missing)} requirement(s) missing — "
                    "Run ▸ Check requirements.txt…"
                )
            cleanup()

        worker.done.connect(done)
        worker.failed.connect(lambda _m: cleanup())
        self._gh_threads.append(thread)
        thread.start()

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
        # The project tree needs its palette themed, not just the stylesheet.
        if hasattr(self, "tree"):
            self.tree.apply_theme(theme)
        # Run/Stop carry status colours that must survive a theme recolour.
        self._update_run_icons()

    # --- updates ---------------------------------------------------------
    def _set_auto_update_check(self, on: bool) -> None:
        self.settings.check_updates = on
        self._status("Start-up update check "
                     f"{'enabled' if on else 'disabled'}.")

    def _start_update_check(self, announce: bool) -> None:
        """Ask GitHub for the latest release on a worker thread.

        *announce* distinguishes the menu action, which always reports back,
        from the start-up check, which only speaks when there is an update.
        """
        from khervepy import updater

        token = self.settings.github_token
        thread = QThread(self)
        worker = _Worker(lambda: updater.fetch_latest(token))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def cleanup():
            thread.quit()
            thread.wait()
            if thread in self._gh_threads:
                self._gh_threads.remove(thread)

        def done(release):
            self._on_update_checked(release, announce)
            cleanup()

        def failed(message):
            if announce:
                self._status(f"Update check failed: {message}")
            cleanup()

        worker.done.connect(done)
        worker.failed.connect(failed)
        self._gh_threads.append(thread)
        thread.start()

    def check_for_updates(self) -> None:
        """Help ▸ Check for updates… — always reports the outcome."""
        self._status("Checking for updates…")
        self._start_update_check(announce=True)

    def _auto_check_updates(self) -> None:
        """The quiet start-up check: at most once a day, silent on failure."""
        from datetime import date

        if not self.settings.check_updates:
            return
        today = date.today().isoformat()
        if self.settings.last_update_check == today:
            return
        self.settings.last_update_check = today
        self._start_update_check(announce=False)

    def _on_update_checked(self, release, announce: bool) -> None:
        from khervepy import updater

        if release is None:
            if announce:
                self._status("Could not reach GitHub to check for updates.")
            return
        if not updater.is_newer(release.version):
            if announce:
                QMessageBox.information(
                    self, "Up to date",
                    f"{__app_name__} {__version__} is the latest version.")
                self._status("KhervePY is up to date.")
            return
        # A version the user chose to skip stays skipped until they ask.
        if not announce and release.version == self.settings.skipped_version:
            return
        self._offer_update(release)

    def _offer_update(self, release) -> None:
        from khervepy import updater

        notes = release.notes
        if len(notes) > 1200:
            notes = notes[:1200] + "\n…"
        box = QMessageBox(self)
        box.setWindowTitle("Update available")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(
            f"<h3>{__app_name__} {release.version} is available</h3>"
            f"<p>You are running {__version__}.</p>")
        if notes:
            box.setDetailedText(notes)

        can_install = updater.is_frozen() and bool(release.installer)
        if can_install:
            install = box.addButton("Download && install",
                                    QMessageBox.ButtonRole.AcceptRole)
        else:
            install = None
        page = box.addButton("Open release page",
                             QMessageBox.ButtonRole.ActionRole)
        skip = box.addButton("Skip this version",
                             QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is install:
            self._install_update(release)
        elif clicked is page:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(release.page))
        elif clicked is skip:
            self.settings.skipped_version = release.version
            self._status(f"Skipping {release.version}.")

    def _install_update(self, release) -> None:
        """Download the installer with a progress dialog, then hand over."""
        from PyQt6.QtWidgets import QProgressDialog
        from khervepy import updater

        progress = QProgressDialog(
            f"Downloading {__app_name__} {release.version}…", "Cancel", 0, 100,
            self)
        progress.setWindowTitle("Updating")
        progress.setMinimumDuration(0)
        progress.setValue(0)

        def report(done, total):
            if progress.wasCanceled():
                return False
            if total:
                progress.setValue(int(100 * done / total))
            progress.setLabelText(
                f"Downloading {__app_name__} {release.version}… "
                f"{done / 1_048_576:.1f} MB")
            QApplication.processEvents()
            return True

        try:
            path = updater.download(release.installer, report)
        except InterruptedError:
            self._status("Update cancelled.")
            return
        except Exception as exc:
            progress.close()
            QMessageBox.warning(
                self, "Download failed",
                f"Could not download the update:\n{exc}\n\n"
                "You can install it by hand from the release page.")
            return
        finally:
            progress.close()

        answer = QMessageBox.question(
            self, "Install now?",
            f"{__app_name__} {release.version} has been downloaded.<br><br>"
            "The installer needs to replace the running program, so KhervePY "
            "will close.<br><br>Save any work first — close now and install?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if answer != QMessageBox.StandardButton.Yes:
            self._status(f"Installer saved to {path}")
            return
        if not updater.launch_installer(path):
            QMessageBox.warning(
                self, "Could not start the installer",
                f"The download is at:\n{path}\n\nRun it by hand to update.")
            return
        self.close()

    def about(self) -> None:
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<h3>{__app_name__} {__version__}</h3>"
            "<p>A lightweight, GitHub-first Python IDE — part of the "
            "<b>KherveTools</b> family.</p>"
            "<p><b>Features:</b> tabbed QScintilla editor with syntax "
            "highlighting and themes, project explorer with full file "
            "operations, integrated Git &amp; GitHub (graph, commit, "
            "push/pull, branches, clone/fork), run &amp; debug, an integrated "
            "terminal, package/venv management, uncommitted-change indicators, "
            "and a multi-provider <b>AI coding assistant</b> "
            "(Claude, OpenAI, Mistral, Ollama).</p>"
            "<p>Built with Python + PyQt6 + QScintilla.</p>"
            "<p>Copyright © 2026 Gwilherm Kerherve<br>"
            "Licensed under the "
            "<a href='https://www.gnu.org/licenses/gpl-3.0.html'>GNU GPL v3</a>"
            " or later.</p>"
            "<p><a href='https://github.com/gkerherve/KhervePY'>"
            "github.com/gkerherve/KhervePY</a></p>",
        )

    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        for path in self.settings.recent_projects():
            act = self.recent_menu.addAction(path)
            act.triggered.connect(lambda _=False, p=path: self.set_project_root(p))

    def _status(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 8000)

    # --- compact "run & commit" cockpit ----------------------------------
    # Small enough to sit beside another window on a laptop screen; the two
    # panels still have room, and any resize is remembered from then on.
    _COMPACT_SIZE = (720, 420)

    def enter_compact_mode(self) -> None:
        """Collapse to a small window: Output left, Log + commit message right."""
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
                  self.diff_dock, self.git_dock, self.ai_dock):
            d.hide()

        # Left: Output — the cockpit exists to watch a run.  Right: the Log,
        # whose own splitter puts the commit graph on top and the full commit
        # message underneath.
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.output_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.log_dock)
        self.commit_log.set_compact(True)
        for d in (self.output_dock, self.log_dock):
            d.show()
        self.output_dock.raise_()

        self.compact_toolbar.show()
        # Drop the layout-derived minimum: it was computed for the tab area and
        # dock furniture now hidden, and would pin the window far wider than
        # these two panels need. Qt recomputes it from the cockpit's own
        # contents, which is what lets the window be dragged genuinely small.
        self.setMinimumSize(QSize(0, 0))

        # Reuse the size, on-screen position and column split from last time.
        cgeom = self.settings.restore_compact_geometry()
        cstate = self.settings.restore_compact_state()
        if cgeom is not None:
            self.restoreGeometry(cgeom)
        else:
            self.resize(*self._COMPACT_SIZE)
        if cstate is not None:
            self.restoreState(cstate)
        else:
            # First time in the cockpit: Qt's default split leaves the Log too
            # narrow for its graph columns. Split closer to even; the user's own
            # drag is remembered from then on.
            self.resizeDocks(
                [self.output_dock, self.log_dock], [55, 45],
                Qt.Orientation.Horizontal,
            )

    def exit_compact_mode(self) -> None:
        """Return to the full editor, restoring the pre-compact layout."""
        if not self._compact:
            return
        # Remember the compact window's size, position and column split.
        self.settings.save_compact_geometry(self.saveGeometry())
        self.settings.save_compact_state(self.saveState())
        self._compact = False
        self.commit_log.set_compact(False)
        self.compact_toolbar.hide()
        # Clear rather than restore: the full window's minimum is Qt's, derived
        # from the layout, so it recomputes correctly once the editor and docks
        # are visible again. Pinning the old numbers back would freeze whatever
        # minimum happened to apply when the cockpit was entered.
        self.setMinimumSize(QSize(0, 0))
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

    def _save_open_files(self) -> None:
        """Remember the open editor tabs (and the active one) for next launch."""
        paths = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeEditor) and w.path:
                paths.append(w.path)
        self.settings.open_files = paths
        cur = self.current_editor()
        self.settings.active_file = cur.path if cur and cur.path else ""

    def _restore_open_files(self) -> None:
        """Reopen the previous session's tabs that belong to this project."""
        for path in self.settings.open_files:
            if os.path.isfile(path) and self._is_in_project(path):
                self.open_path(path)
        active = self.settings.active_file
        if active and os.path.isfile(active) and self._is_in_project(active):
            self.open_path(active)  # dedups → just re-focuses the tab

    def closeEvent(self, event) -> None:
        # Flush path-backed editors silently (auto-save); prompt only for
        # untitled buffers that were never given a path.
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if not (isinstance(w, CodeEditor) and w.isModified()):
                continue
            if w.path:
                try:
                    w.save()
                except OSError:
                    pass
                continue
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
            if answer == QMessageBox.StandardButton.Save:
                self.save_current()
        # Leave compact mode first, so the persisted layout is the full one.
        if self._compact:
            self.exit_compact_mode()
        # Save the layout *before* tearing down child processes, so a slow or
        # failing stop() can never cost the user their window positions.
        self._save_window()
        self._save_open_files()
        self.terminal.stop()
        self.debugger.stop()
        self.ai_chat.stop()
        for thread in list(self._gh_threads):
            thread.quit()
            thread.wait()
        super().closeEvent(event)
