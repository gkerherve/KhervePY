# KhervePY — project rules for Claude

KhervePY is a member of the **KherveTools** family and follows the same
conventions as the other tools (KherveBook, KherveSheet, …).

## What KhervePY is

A lightweight, GitHub-first Python IDE written in **Python + Qt** (PyQt6 +
QScintilla). It is deliberately smaller than PyCharm/VS Code because code is now
written with Claude Code; KhervePY covers editing, highlighting and the
Git/GitHub workflow.

## Workflow rules (KherveTools)

1. **Commit and push on every message.** Each change the user asks for ends with
   a commit and a push to the designated branch.
2. **Bump the version on every push.** Update `__version__` in
   `khervepy/__init__.py` and `version` context in `pyproject.toml`/`CHANGELOG.md`
   before each push. Use semantic-ish bumps: patch for fixes, minor for features.
3. **Keep `CHANGELOG.md` current** — add an entry describing what changed for the
   new version.
4. **Never overwrite user data.** File saves preserve content and use UTF-8 with
   `\n` line endings.
5. **Match the house style.** Every module starts with the GPL v3 header block
   (see existing files) and `Copyright (C) 2026 Gwilherm Kerherve`.

## Code conventions

- Python 3.10+ with `from __future__ import annotations`.
- Qt bindings: **PyQt6**; editor component: **QScintilla** (`PyQt6.Qsci`).
- Keep Qt imports lazy where a module may be imported headless (e.g. `themes`,
  `lexers`) so tooling can introspect without a display.
- Network/long operations run on a worker thread (`QThread`/`QProcess`), never on
  the GUI thread.
- Secrets (GitHub token) live in `QSettings`, never in the repo.

## Layout

```
KhervePY.py            entry-point shim  ->  khervepy.app.main()
khervepy/
  __init__.py          __version__ lives here
  app.py               main(): builds QApplication + MainWindow
  main_window.py       toolbar, tabs, docks, menus, actions
  editor.py            CodeEditor (QsciScintilla)
  lexers.py            extension -> lexer mapping
  themes.py            theme catalogue + apply_theme()
  file_tree.py         project browser dock
  git_backend.py       git CLI wrapper + GitHub REST API
  git_panel.py         Git/GitHub dock UI
  package_manager.py   venv + pip dialog
  settings.py          QSettings façade
```

## Running

```bash
pip install -r requirements.txt
python KhervePY.py
```
