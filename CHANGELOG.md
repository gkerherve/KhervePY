# Changelog

All notable changes to KhervePY are recorded here. The version number is bumped
on every push, per the KherveTools workflow.

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
