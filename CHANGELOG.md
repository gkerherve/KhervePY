# Changelog

All notable changes to KhervePY are recorded here. The version number is bumped
on every push, per the KherveTools workflow.

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
