# Changelog

All notable changes to KhervePY are recorded here. The version number is bumped
on every push, per the KherveTools workflow.

## 0.32.0 — 2026-07-17

### Added
- **File menu entries**: **New Instance** launches a second KhervePY window as a
  separate process; **New Python File…** creates an empty `.py` file on disk
  (UTF-8, `\n` line endings) and opens it in a tab; **Open File Location** reveals
  the current file in the OS file browser (Explorer `/select`, Finder `-R`, or
  `xdg-open`), falling back to the project root when no file is focused.

## 0.31.0 — 2026-07-16

### Changed
- **Type directly in the Terminal**: the separate "Type a command" box is gone.
  The console view is now editable in place, like a real terminal — commands are
  typed on the shell's own prompt line. Scrollback is protected: editing keys
  only act after the shell's last output, and clicking into the history then
  typing returns you to the input zone. Up/Down still recall history.
- **No duplicated commands**: the shell echoes back whatever it reads from the
  pipe, which doubled the text already on screen. The first echoed copy is now
  dropped, so a session reads like a native shell.
- **Sharp icons at every size**: `khervepy.ico` now carries a native render at
  16/24/32/48/64/128/256px instead of one 256px image for Windows to downscale
  (and is 23 KB rather than 270 KB).

## 0.30.2 — 2026-07-16

### Fixed
- **Terminal would not accept typing**: clicking the (read-only) output view
  took focus and swallowed keystrokes. The view and the dock now proxy focus to
  the command line, so typing anywhere in the Terminal reaches the shell.
- **Icon rendered as tofu boxes**: `make_icon.py` forced Qt's `offscreen`
  platform, which has no font database on Windows, and asked for a
  comma-separated font list Qt cannot resolve as a family name.

### Changed
- **Application icon** is now a three-tone **KPy** wordmark (Kherve white +
  Python blue/yellow) instead of "Py".

## 0.30.1 — 2026-07-14

### Fixed
- **Windows encoding crash**: child-process output (git/pip) is now decoded as
  UTF-8 with `errors="replace"`, fixing `UnicodeDecodeError` reader-thread
  tracebacks (cp1252 could not decode bytes like `0x81`).
- **Yellow folder icons**: the Project tree now uses themed monochrome
  folder/file icons instead of the OS's yellow folders, matching the theme.

## 0.30.0 — 2026-07-14

### Added
- **Hideable menu bar**: View → Menu Bar (or **Ctrl+M**) toggles it; the state
  is remembered, and Ctrl+M still works while it is hidden.

### Fixed
- The **Project tree** now follows the editor theme properly (its palette is
  themed, not just the stylesheet), so it no longer shows a light background
  under dark themes.

## 0.29.0 — 2026-07-14

### Added
- **AI agent mode** (on by default, toggle in the AI dock): the assistant can
  now act on your project through tools instead of only chatting —
  - `get_open_files` — see which files are open and which is active
  - `read_file` / `write_file` — view and edit project files directly
  - `git_commit` — stage all changes and commit
  Each tool action is logged in the transcript; edited files that are open are
  reloaded automatically and the Git views refresh. Works with Claude, OpenAI,
  Mistral and Ollama (tool-capable models). Writes are sandboxed to the project
  folder. Uncheck "Agent" for plain chat.

## 0.28.1 — 2026-07-14

### Fixed
- AI chat never responded: worker completions were running on the worker
  thread and deadlocking on `thread.wait()`, so replies never rendered.
  Completions are now dispatched to the GUI thread.

### Added
- **Stop** button in the AI chat to cancel an in-flight request (its result is
  discarded), plus a "…is thinking…" indicator while waiting.

## 0.28.0 — 2026-07-14

### Added
- **AI coding assistant** in a dock tabbed with the Terminal. Chat with a model
  to write code or check mistakes:
  - Providers: **Claude (Anthropic)**, **OpenAI**, **Mistral**, and local
    **Ollama** (no key). Switch freely.
  - **↻ Models** button refreshes the live model list per provider.
  - **Keys…** dialog stores API keys in QSettings (never in the repo); **?**
    explains how to get a key for each provider.
  - **Attach current file** sends the active editor file for review.
  - Ctrl+Enter sends; network calls run off the UI thread.
- Help menu additions: AI Assistant, Get an API key…, AI API Keys…, and a
  richer **About** dialog (features, links, GPL-3).

### Changed
- Run menu gains **AI Assistant**.

## 0.27.1 — 2026-07-13

### Changed
- The branch-chip dropdown now colours each branch with a dot matching the
  commit graph: green for the current branch, blue for other local branches,
  purple for remotes.

## 0.27.0 — 2026-07-13

### Changed
- Log ref markers are now small **coloured dots** in the graph column, so the
  column stays narrow. The full branch/tag names are described in the row
  **tooltip** and as a **Refs:** line atop the commit-message panel.
- **LICENSE** now contains the full GNU GPL v3 text (was a short notice).

## 0.26.0 — 2026-07-13

### Added
- **Full file-explorer operations** in the Project tree:
  - Right-click menu: New File, New Folder, Cut, Copy, Paste, Duplicate,
    Rename, Delete, Copy Path, Reveal in File Explorer.
  - Shortcuts: `F2` rename, `Delete`, `Ctrl+C`/`Ctrl+X`/`Ctrl+V`.
  - **Drag-and-drop** to move files/folders (and drop external files in).
  - Copy/duplicate auto-dedupes names ("… copy", "… copy 2"). New files open
    in the editor. Git-status colours refresh after each operation.

## 0.25.0 — 2026-07-13

### Changed
- Log layout reworked: ref badges (branch/tag) now live in the **Graph**
  column beside the rails, so the **Description** column shows only the commit
  subject. Columns are reordered to **Graph › Description › Date › Author**, and
  the author is shown compactly as **G Kerherve** (first initial + surname).

## 0.24.2 — 2026-07-13

### Fixed
- The latest commit's subject is no longer hidden behind ref badges. Badges are
  now clipped to the Description column, `origin/HEAD` is dropped, a remote that
  mirrors the current branch collapses to `origin`, long badges are elided, and
  the subject always keeps room (with a `…` marker when refs overflow).

## 0.24.1 — 2026-07-13

### Changed
- Log dates are now friendly and include the time: **Today 16:26**,
  **Yesterday 23:41**, a weekday (e.g. **Mon 14:07**) within the last week,
  else the plain date.

## 0.24.0 — 2026-07-13

### Added
- **Code menu** with the standard PyCharm/VS Code editor shortcuts:
  - Comment with Line Comment — `Ctrl+/` (language-aware token, toggles,
    keeps the selection)
  - Comment with Block Comment — `Ctrl+Shift+/`
  - Duplicate Line/Selection — `Ctrl+D`
  - Delete Line — `Ctrl+Shift+K`
  - Move Line Up / Down — `Alt+Shift+Up` / `Alt+Shift+Down`
  - Collapse/Expand fold — `Ctrl+.`
  - Collapse All / Expand All — `Ctrl+Shift+-` / `Ctrl+Shift+=`
  - Go to Line… — `Ctrl+G`

## 0.23.0 — 2026-07-13

### Added
- **Uncommitted-change indicators**, refreshed live (debounced) as you edit:
  - **Editor change bar**: a thin gutter next to the line numbers marks lines
    added (green), modified (blue) or deleted (red) versus the last commit
    (HEAD). New/untracked files show all lines green.
  - **Project tree colours**: changed files are tinted by git status —
    added/untracked green, modified blue, deleted red, conflicts amber — and
    folders that contain changes are tinted too.
- Backed by `git_backend.status_map()` and `git_backend.file_at_head()`.

## 0.22.3 — 2026-07-13

### Changed
- Installer now creates shortcuts you can actually find: a **Desktop** icon
  (offered pre-checked) and **Start-menu** entries for KhervePY and its
  uninstaller. Add/Remove Programs also shows the app icon
  (`UninstallDisplayIcon`).

## 0.22.2 — 2026-07-13

### Fixed
- Session restore no longer reopens files from a **different** project. On
  launch, only saved tabs that live inside the current project are restored, so
  a stray file like another project's `Main.py` won't linger. (The "close
  foreign tabs on project switch" logic now shares the same in-project check.)

## 0.22.1 — 2026-07-13

### Changed
- `build.py --installer` now finds the Inno Setup compiler (`ISCC.exe`) in its
  usual install locations — including per-user installs under
  `%LOCALAPPDATA%\Programs\Inno Setup 6` — instead of only checking PATH. This
  lets it build `Output\KhervePY-Setup-<version>.exe` out of the box.

## 0.22.0 — 2026-07-13

### Changed
- **Opening a different project closes files that don't belong to it.** When
  you switch project roots, editor tabs whose file lives outside the new
  project are closed (auto-saved first); untitled buffers and files inside the
  new project stay open.

## 0.21.0 — 2026-07-13

### Fixed
- **Frozen build no longer flashes console windows.** Every child process
  (git, the integrated shell, Python, pip) is now spawned with
  `CREATE_NO_WINDOW` on Windows, so the packaged `.exe` stops popping/closing
  console windows on startup and during git refreshes.
- **Run / Debug / auto-install now find a real Python in the frozen build.**
  Previously `sys.executable` pointed at `KhervePY.exe`, so Run relaunched the
  IDE instead of executing your script (it looked "stuck on KhervePY"). It now
  resolves a genuine interpreter — the project's `venv`/`.venv` first, then any
  `python` on PATH — and shows a clear message if none is found.

### Added
- `khervepy/proc.py`: shared helpers for console suppression and Python-
  interpreter discovery.

## 0.20.1 — 2026-07-13

### Changed
- Default theme is now **GitHub Dark** (was Darcula). Applies to fresh
  installs; an already-chosen theme is preserved.

## 0.20.0 — 2026-07-13

### Added
- **Auto-save**: edits to a saved file are written to disk automatically
  (debounced ~250 ms after you stop typing). Closing a tab or the window now
  flushes path-backed files silently instead of prompting; only untitled
  buffers still ask.
- **Compact mode remembers its window**: the mini cockpit reopens at the same
  size, on-screen position and Terminal↔Log column split you left it at.

## 0.19.0 — 2026-07-13

### Added
- **Session memory for open files**: the editor tabs you had open (and which
  one was active) are remembered on close and reopened on the next launch.

## 0.18.3 — 2026-07-13

### Changed
- The Log dock's columns (Graph, Description, Author, Date) are now
  user-resizable — drag any header divider to adjust widths.

## 0.18.2 — 2026-07-13

### Changed
- Compact cockpit layout: **Terminal** on the left, **Log** (commit graph +
  full commit message) on the right.

## 0.18.0 — 2026-07-13

### Added
- **Compact "Run & Commit" cockpit**: a toggle pinned to the far right of the
  toolbar (Ctrl+Shift+M) shrinks the window to a small cockpit, with its own
  minimal toolbar carrying the green **Run**, red **Stop**, and a **Maximise**
  button that restores the full editor and its exact previous layout. The full
  layout is always persisted, even if you quit while compact.

## 0.17.0 — 2026-07-13

### Added
- **Commit message panel** in the Log dock, between the commit graph and the
  Files-changed tree: selecting a commit shows its full subject + body (the
  graph's Description column is truncated). Backed by
  `git_backend.commit_message()`.

## 0.16.0 — 2026-07-13

### Added
- **Stop button** on the toolbar (Ctrl+F2) that kills the program launched by
  Run. It is red and clickable while a program is running, and muted/disabled
  when nothing is running.
- The **Run** icon turns **green** while a program is executing and returns to
  the theme colour when it exits. Both status colours survive theme switches.

## 0.15.0 — 2026-07-13

### Added
- **Auto-install missing modules**: when a run fails with
  `ModuleNotFoundError`, KhervePY now offers to `pip install` the missing
  module into the interpreter that ran the script, streams the install into
  the Output panel, and offers to re-run once it succeeds. A small
  import-name → pip-name table handles the common mismatches (`cv2` →
  `opencv-python`, `PIL` → `pillow`, `sklearn` → `scikit-learn`, …).

### Changed
- **Reliable window-layout memory**: the dock/toolbar layout and window
  geometry are now saved *before* child processes are torn down at close, and
  also on application quit, so panel positions (Project, Log, Git / GitHub,
  Output, Terminal, …) are restored dependably on the next launch.

## 0.14.0 — 2026-07-13

### Added
- **Files-changed tree** under the commit graph: selecting a commit shows the
  files it touched as a folder tree (status-coloured); double-click a file to
  view that file's patch in the Diff dock.
- `git_backend.commit_files()` and `commit_file_diff()`.

### Changed
- **Curved branch rails** — the commit graph now draws smooth bezier corners
  between lanes instead of straight diagonals, matching VS Code's Git Graph.
- **Whole-window theming**: the selected editor theme now dresses the entire
  window — toolbar, docks, menus, tabs, tree/list panels, inputs, buttons,
  scrollbars and status bar — via `themes.window_stylesheet()`. Toolbar icons
  are recoloured to the theme on every switch.
- The **Changes** (staging) panel is hidden by default; reopen it from
  View → Git / GitHub. History and the branch chip's Push/Pull/Clone/Fork are
  unaffected.

## 0.13.0 — 2026-07-13

### Changed
- The **Log** dock is now a **VS Code–style commit graph**: coloured branch
  lane rails with commit nodes, ref badges (current branch green, local blue,
  remote purple, tags gold), plus author and date columns. An **"All branches"**
  toggle switches between the whole graph and the current branch. Double-click a
  commit to view its patch in the Diff dock.
- New `khervepy/commit_graph.py` (lane-layout algorithm + painting delegate) and
  `git_backend.log_graph()` (commits with parents and decorations).

## 0.12.0 — 2026-07-13

### Added
- **Six more highlighting themes** (13 total): Nord, Gruvbox Dark, Tokyo Night,
  GitHub Dark, Material Ocean and Cobalt2. Each colours keywords, strings,
  numbers, class/function names, decorators and operators distinctly, and all
  appear in the toolbar theme picker.

## 0.11.0 — 2026-07-13

### Added
- **Commit history ("Log") dock**, tabbed with the Git panel on the right.
  Lists recent commits with branch/tag decorations, author and date; the
  current HEAD refs are highlighted. Double-click a commit to view its full
  patch in the Diff dock. Refreshes automatically after any VCS action and when
  a project is opened.
- `git_backend.log_entries()` and `show_commit()`.

## 0.10.0 — 2026-07-13

### Added
- **PyCharm-style Git branch chip** on the toolbar (`khervepy/branch_widget.py`).
  Shows the current branch — auto-detected the moment a local folder is opened —
  and drops down to a menu that mirrors PyCharm's: a header showing the
  signed-in GitHub account and the repository's remote, then Update (Pull),
  Commit, Push, Fetch and New Branch, followed by checkout lists of **Local**
  branches (current one ticked) and **Remote** branches (checked out as new
  tracking branches). When the folder isn't a repo yet, the menu offers Clone,
  Fork or "Create Git repository here".
- `git_backend` helpers: `remote_branches()`, `fetch()`, `init()`,
  `checkout_track()`; a new `branch` glyph icon.
- The Git panel emits a `changed` signal so the chip stays in sync after any
  VCS action.

## 0.9.0 — 2026-07-13

### Added
- **GitHub token dialog** (`GitHub → Set Token…`): a real dialog replacing the
  plain prompt, with a description, a **"Create a token on GitHub"** link that
  opens the pre-filled classic-token page (repo scope), a show/hide reveal
  toggle, and a **"Test token"** button that verifies the token off-thread and
  reports the authenticated username.
- **Persistent GitHub indicator** in the status bar showing "GitHub: \<user\>",
  "token set" or "not signed in"; click it to open the token dialog. On startup
  a stored-but-unverified token is confirmed quietly in the background.

## 0.8.1 — 2026-07-13

### Changed
- Toolbar is now **icon-only** (no text labels); each action's name and
  shortcut show as a hover tooltip. Icon size raised to 24 px for a clear,
  comfortable target, and icons are rendered at exact sizes (16/24/32/48) so
  they stay crisp.

## 0.8.0 — 2026-07-13

### Added
- **Toolbar icons**: every toolbar action now carries a small line-glyph icon
  (open folder/file, new, save, run, debug, terminal, find, replace,
  find-in-files, search, commit+push, clone, fork, packages). Icons are drawn
  on the fly in the toolbar's text colour (`khervepy/icons.py`) so they suit
  both light and dark OS themes — no image assets to ship.

### Changed
- Toolbar icons are rendered deliberately small (14 px, vs the usual ~24 px)
  for a compact, dense toolbar.

## 0.7.0 — 2026-07-13

### Added
- **Packaging**: freeze KhervePY into a standalone app and build distributables.
  - `packaging/khervepy.spec` — PyInstaller one-folder, windowed build.
  - `packaging/khervepy.iss` — Inno Setup installer script (Windows), version
    injected at build time; bundles a Start-Menu entry, optional desktop icon
    and the GPL licence page.
  - `build.py` — cross-platform orchestrator: freezes the app, writes a
    `KhervePY-<version>-<platform>.zip`, and builds the installer when run on
    Windows with Inno Setup present (`--installer`, `--clean` flags).
  - `packaging/make_icon.py` plus generated `khervepy.png` / `khervepy.ico`
    (a two-tone "Py" wordmark on an editor tile); the app now shows its icon.
  - `requirements-dev.txt` pinning PyInstaller.

## 0.6.0 — 2026-07-13

### Added
- **Diff viewer** for the Git panel: double-click any changed file to see its
  unified diff in a bottom dock, with added/removed lines and hunk headers
  colourised. Handles staged, working-tree and untracked/new files (the latter
  shown as all-additions via `--no-index`).
- `git_backend.diff_file()` for single-file diffs with an untracked fallback.

## 0.5.0 — 2026-07-13

### Added
- **Python debugger** dock driven by the standard-library `pdb` (Shift+F5).
  Runs the current file under `python -m pdb` in a `QProcess`; controls for
  Continue, Step, Next and Return; "Break here" sets a breakpoint at the caret;
  a raw pdb command line for anything else (`p var`, `l`, `w`, …). Follows the
  active project directory.

## 0.4.0 — 2026-07-13

### Added
- **Integrated terminal** dock (Ctrl+`), tabbed with the Output pane. Runs a
  persistent interactive shell via `QProcess`, streams merged stdout/stderr,
  and pipes typed commands to its stdin. Command history (Up/Down), Clear and
  Restart buttons. Follows the active project directory (`cd` on project
  switch). Line-oriented — full-screen/curses programs are not supported.

## 0.3.0 — 2026-07-13

### Added
- **Global search dock** (Ctrl+Shift+S): a persistent, dockable project-wide
  search tabbed behind the project tree. Runs on a worker thread so large
  projects stay responsive, streams results per file into a tree, and jumps to
  the matching line on double-click. Case, whole-word and regex toggles.
- Factored the file-walk and query-compilation helpers so the search dock and
  the Find-in-Files dialog share one implementation.

## 0.2.0 — 2026-07-13

### Added
- In-editor **Find/Replace bar** (Ctrl+F / Ctrl+H) with case, whole-word and
  regex toggles, find next/previous and replace-all, driven by QScintilla's
  own search so matches highlight and scroll into view.
- **Find / Replace in Files** dialog (Ctrl+Shift+F): search every text file in
  the project, grouped results with match counts, double-click to jump to the
  line, and project-wide replace that preserves UTF-8 + `\n` line endings.
- New **Edit** menu hosting the find/replace actions.

## 0.1.0 — 2026-07-12

Initial release. First working foundation of the KhervePY IDE.

### Added
- Qt (PyQt6 + QScintilla) application shell with a horizontal toolbar.
- Tabbed multi-file editor with modified-state markers and unsaved-change guards.
- Project file tree dock that opens files on double-click.
- Syntax highlighting for Python, JS/TS, C/C++/C#/Java/Go/Rust, HTML, CSS, JSON,
  Markdown, Bash, YAML, SQL and XML.
- Seven highlighting themes: Darcula, One Dark, Monokai, Dracula, Solarized
  Dark/Light and GitHub Light, switchable from the toolbar.
- GitHub / Git dock: branch switching, staging, commit, push, pull, clone, and
  **fork** (via the GitHub REST API).
- One-click "Commit + Push" toolbar action.
- "My Repositories" browser to clone any repo the token can access.
- Environments & Packages dialog: create/select virtualenvs, pip install /
  uninstall, install from requirements.txt, and freeze.
- Run the current Python file with output captured in a dock.
- Persistent settings (theme, token, recent projects, window layout).
