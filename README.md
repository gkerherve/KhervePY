# KhervePY

A lightweight, **GitHub-first** Python IDE built with Python and Qt
(PyQt6 + QScintilla). Part of the KherveTools family.

KhervePY is intentionally *smaller* than PyCharm or VS Code — the heavy lifting
(writing and refactoring code) is now done with Claude Code. KhervePY focuses on
what you still want a desktop editor for: reading and editing files with good
highlighting, and managing your Git/GitHub workflow without leaving the window.

## Features

- **Horizontal toolbar** with the actions you reach for most.
- **Tabbed editor** — open many files side by side, with unsaved-change guards.
- **Project tree** dock for browsing a folder.
- **IDE-grade syntax highlighting** for Python, JavaScript/TypeScript,
  C/C++/C#/Java/Go/Rust, HTML, CSS, JSON, Markdown, Bash, YAML, SQL and XML.
- **Seven themes** — Darcula, One Dark, Monokai, Dracula, Solarized Dark/Light
  and GitHub Light — switchable from the toolbar.
- **GitHub integration** (the headline feature):
  - stage, commit, push, pull, switch/create branches
  - **clone** any repository
  - **fork** a GitHub project into your account (GitHub REST API)
  - browse and clone your own repositories
  - one-click **Commit + Push**
- **Environments & packages** — create/select virtualenvs and pip-install
  libraries from inside the app, or install a `requirements.txt`.
- **Run** the current Python file with captured output.

## Requirements

- Python 3.10+
- PyQt6 and PyQt6-QScintilla

## Install & run

```bash
pip install -r requirements.txt
python KhervePY.py
# or
python -m khervepy
```

You can also pass a file or folder to open on startup:

```bash
python KhervePY.py path/to/project
```

## Building distributables

KhervePY freezes to a standalone app with PyInstaller and ships as a zip and
(on Windows) an Inno Setup installer.

```bash
pip install -r requirements-dev.txt
python build.py              # freeze + KhervePY-<version>-<platform>.zip
python build.py --installer  # also build the Windows installer (needs Inno Setup)
python build.py --clean      # wipe build/ dist/ Output/ first
```

Outputs land in `dist/` (frozen app + zip) and `Output/` (installer). The
installer version is taken from `khervepy/__version__` automatically. To
regenerate the app icon, run `python packaging/make_icon.py`.

## GitHub setup

To clone private repos and to fork projects, add a GitHub personal access token
(with `repo` scope) via **GitHub → Set Token…**. The token is stored in your OS
settings store, never in the repository.

## License

Copyright (C) 2026 Gwilherm Kerherve. Licensed under the GNU GPL v3 or later.
