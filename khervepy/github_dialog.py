"""The GitHub token dialog: paste, test and save a personal access token.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from khervepy import git_backend as gb

# Pre-fills the classic-token page with the repo scope and a name.
CREATE_TOKEN_URL = (
    "https://github.com/settings/tokens/new?scopes=repo&description=KhervePY"
)


class _VerifyWorker(QObject):
    ok = pyqtSignal(str)      # login
    error = pyqtSignal(str)

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    def run(self):
        try:
            user = gb.github_user(self._token)
            self.ok.emit(user.get("login", "?"))
        except Exception as exc:  # surfaced to the user
            self.error.emit(str(exc))


class TokenDialog(QDialog):
    """Collect, test and (on accept) hand back a GitHub token."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.verified_login: str | None = None
        self._thread: QThread | None = None

        self.setWindowTitle("GitHub token")
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        intro = QLabel(
            "KhervePY uses a GitHub <b>personal access token</b> to fork "
            "repositories, list your repositories and clone private repos. "
            "The token is stored in your OS settings, never in the repo."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        link = QLabel(
            f'<a href="{CREATE_TOKEN_URL}">Create a token on GitHub '
            "(classic, “repo” scope)…</a>"
        )
        link.setOpenExternalLinks(False)
        link.linkActivated.connect(lambda url: QDesktopServices.openUrl(_to_qurl(url)))
        layout.addWidget(link)

        layout.addWidget(QLabel("Personal access token (repo scope):"))

        field_row = QHBoxLayout()
        self.field = QLineEdit(self.settings.github_token)
        self.field.setEchoMode(QLineEdit.EchoMode.Password)
        self.field.setPlaceholderText("ghp_… or github_pat_…")
        self.field.textChanged.connect(self._on_changed)
        field_row.addWidget(self.field, 1)

        self.reveal_btn = QPushButton("Show")
        self.reveal_btn.setCheckable(True)
        self.reveal_btn.toggled.connect(self._toggle_reveal)
        field_row.addWidget(self.reveal_btn)

        self.test_btn = QPushButton("Test token")
        self.test_btn.clicked.connect(self._test)
        field_row.addWidget(self.test_btn)
        layout.addLayout(field_row)

        self.result = QLabel(" ")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # --- helpers ---------------------------------------------------------
    def token(self) -> str:
        return self.field.text().strip()

    def _on_changed(self) -> None:
        # A changed token invalidates any previous verification.
        self.verified_login = None
        self.result.setText(" ")

    def _toggle_reveal(self, shown: bool) -> None:
        self.field.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )
        self.reveal_btn.setText("Hide" if shown else "Show")

    def _test(self) -> None:
        token = self.token()
        if not token:
            self.result.setText("<span style='color:#C05050'>Enter a token first.</span>")
            return
        if self._thread is not None:
            return
        self.result.setText("Testing…")
        self.test_btn.setEnabled(False)

        self._thread = QThread(self)
        self._worker = _VerifyWorker(token)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.ok.connect(self._on_ok)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    def _on_ok(self, login: str) -> None:
        self.verified_login = login
        self.result.setText(
            f"<span style='color:#3FA34D'>✓ Authenticated as <b>{login}</b></span>"
        )
        self._finish_test()

    def _on_error(self, message: str) -> None:
        self.verified_login = None
        self.result.setText(f"<span style='color:#C05050'>✗ {message}</span>")
        self._finish_test()

    def _finish_test(self) -> None:
        self.test_btn.setEnabled(True)
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None


def _to_qurl(url: str):
    from PyQt6.QtCore import QUrl

    return QUrl(url)
