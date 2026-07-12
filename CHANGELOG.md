# Changelog

All notable changes to KhervePY are recorded here. The version number is bumped
on every push, per the KherveTools workflow.

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
