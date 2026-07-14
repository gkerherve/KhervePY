"""The AI assistant dock: a multi-provider coding chat.

Sits in the bottom dock area (tabbed with the Terminal). Pick a provider
(Claude, OpenAI, Mistral or a local Ollama), refresh the model list, and chat.
Optionally attach the current editor file so the assistant can review it for
mistakes. API keys are stored in ``QSettings`` and entered through the Keys
dialog; network calls run on a worker thread.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import html

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QKeySequence, QShortcut
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from khervepy import ai_backend as ai


class _Worker(QObject):
    """Runs a callable off the GUI thread and reports the outcome."""

    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as exc:  # noqa: BLE001 — surfaced to the user
            self.failed.emit(str(exc))


class AIKeysDialog(QDialog):
    """Enter/replace the API key for each provider."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("KhervePY — AI API Keys")
        self.resize(560, 260)
        self._edits: dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        for pid in ai.PROVIDER_ORDER:
            meta = ai.PROVIDERS[pid]
            row = QHBoxLayout()
            edit = QLineEdit(self.settings.api_key(pid))
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            if not meta["needs_key"]:
                edit.setPlaceholderText("No key needed — Ollama runs locally")
                edit.setEnabled(False)
            self._edits[pid] = edit
            row.addWidget(edit, 1)
            get = QPushButton("Get a key…")
            get.clicked.connect(lambda _=False, u=meta["key_url"]:
                                QDesktopServices.openUrl(QUrl(u)))
            row.addWidget(get)
            box = QWidget()
            box.setLayout(row)
            form.addRow(meta["label"] + ":", box)
        layout.addLayout(form)

        note = QLabel(
            "Keys are stored in your OS settings store, never in the project."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        for pid, edit in self._edits.items():
            if ai.PROVIDERS[pid]["needs_key"]:
                self.settings.set_api_key(pid, edit.text().strip())
        self.accept()


class AIChat(QWidget):
    """Provider-agnostic coding chat with a model picker and refresh."""

    status_message = pyqtSignal(str)

    def __init__(self, settings, context_getter=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        # context_getter() -> (filename, text) for the current editor, or None
        self._context_getter = context_getter
        self._history: list[dict] = []
        self._threads: list[QThread] = []
        self._jobs: dict[int, tuple] = {}
        self._gen = 0
        self._busy = False

        self._build_ui()
        self._load_provider(self.settings.ai_provider)

    # --- UI --------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Provider / model / actions row.
        top = QHBoxLayout()
        self.provider_box = QComboBox()
        for pid in ai.PROVIDER_ORDER:
            self.provider_box.addItem(ai.PROVIDERS[pid]["label"], pid)
        self.provider_box.currentIndexChanged.connect(self._on_provider_changed)
        top.addWidget(self.provider_box)

        self.model_box = QComboBox()
        self.model_box.setMinimumWidth(180)
        self.model_box.setEditable(True)
        top.addWidget(self.model_box, 1)

        self.refresh_btn = QPushButton("↻ Models")
        self.refresh_btn.setToolTip("Refresh the model list for this provider")
        self.refresh_btn.clicked.connect(self._refresh_models)
        top.addWidget(self.refresh_btn)

        keys_btn = QPushButton("Keys…")
        keys_btn.clicked.connect(self.open_keys)
        top.addWidget(keys_btn)

        help_btn = QPushButton("?")
        help_btn.setFixedWidth(28)
        help_btn.setToolTip("How to get an API key")
        help_btn.clicked.connect(self.show_help)
        top.addWidget(help_btn)
        layout.addLayout(top)

        # Transcript.
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        layout.addWidget(self.view, 1)

        # Input row.
        self.context_cb = QCheckBox("Attach current file")
        self.context_cb.setToolTip(
            "Send the active editor file so the assistant can review it"
        )
        layout.addWidget(self.context_cb)

        bottom = QHBoxLayout()
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "Ask for code or paste an error…  (Ctrl+Enter to send)"
        )
        self.input.setFixedHeight(64)
        mono = QFont("Consolas, DejaVu Sans Mono, monospace", 10)
        self.input.setFont(mono)
        bottom.addWidget(self.input, 1)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send)
        bottom.addWidget(self.send_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("Cancel the current request")
        self.stop_btn.clicked.connect(self._stop)
        bottom.addWidget(self.stop_btn)
        layout.addLayout(bottom)

        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(seq), self.input,
                      activated=self._send)

        self._system_line(
            "AI assistant ready. Pick a provider and model, then ask away. "
            "Set an API key via ‘Keys…’ (Ollama needs none)."
        )

    # --- provider / model handling ---------------------------------------
    def _provider(self) -> str:
        return self.provider_box.currentData()

    def _on_provider_changed(self) -> None:
        self._load_provider(self._provider())

    def _load_provider(self, provider: str) -> None:
        idx = self.provider_box.findData(provider)
        if idx >= 0 and self.provider_box.currentIndex() != idx:
            self.provider_box.setCurrentIndex(idx)
            return
        self.settings.ai_provider = provider
        cached = self.settings.ai_models(provider)
        models = cached or ai.PROVIDERS[provider]["defaults"]
        self.model_box.blockSignals(True)
        self.model_box.clear()
        self.model_box.addItems(models)
        last = self.settings.ai_model(provider)
        if last:
            i = self.model_box.findText(last)
            if i >= 0:
                self.model_box.setCurrentIndex(i)
            else:
                self.model_box.setEditText(last)
        self.model_box.blockSignals(False)

    def _refresh_models(self) -> None:
        provider = self._provider()
        key = self.settings.api_key(provider)
        if ai.PROVIDERS[provider]["needs_key"] and not key:
            self._need_key(provider)
            return
        self.refresh_btn.setEnabled(False)
        self.status_message.emit(f"Refreshing {provider} models…")
        self._run(
            lambda: ai.list_models(provider, key),
            lambda models: self._models_refreshed(provider, models),
            self._refresh_failed,
        )

    def _models_refreshed(self, provider: str, models: list[str]) -> None:
        self.refresh_btn.setEnabled(True)
        if not models:
            self._system_line(f"No models returned for {provider}.")
            return
        self.settings.set_ai_models(provider, models)
        current = self.model_box.currentText()
        self.model_box.blockSignals(True)
        self.model_box.clear()
        self.model_box.addItems(models)
        if current in models:
            self.model_box.setCurrentText(current)
        self.model_box.blockSignals(False)
        self.status_message.emit(f"{len(models)} {provider} model(s).")

    def _refresh_failed(self, msg: str) -> None:
        self.refresh_btn.setEnabled(True)
        self._system_line(f"Could not list models: {msg}")

    # --- chat ------------------------------------------------------------
    def _send(self) -> None:
        if self._busy:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        provider = self._provider()
        key = self.settings.api_key(provider)
        if ai.PROVIDERS[provider]["needs_key"] and not key:
            self._need_key(provider)
            return
        model = self.model_box.currentText().strip()
        if not model:
            QMessageBox.information(
                self, "No model", "Pick or refresh a model first.")
            return

        content = text
        if self.context_cb.isChecked() and self._context_getter:
            ctx = self._context_getter()
            if ctx and ctx[1]:
                name, body = ctx
                content = (f"Here is my current file `{name}`:\n\n```\n{body}\n"
                           f"```\n\n{text}")

        self._history.append({"role": "user", "content": content})
        self._append("user", text)
        self.input.clear()
        self.settings.set_ai_model(provider, model)
        self._set_busy(True)
        self._system_line(
            f"{ai.PROVIDERS[provider]['label']} ({model}) is thinking…")

        messages = list(self._history)
        self._run(
            lambda: ai.chat(provider, key, model, messages),
            self._reply,
            self._chat_failed,
        )

    def _reply(self, text: str) -> None:
        self._history.append({"role": "assistant", "content": text})
        self._append("assistant", text)
        self._set_busy(False)

    def _chat_failed(self, msg: str) -> None:
        # Drop the unanswered user turn so a retry doesn't stack context.
        if self._history and self._history[-1]["role"] == "user":
            self._history.pop()
        self._system_line(f"Error: {msg}")
        self._set_busy(False)

    def clear_chat(self) -> None:
        self._history.clear()
        self.view.clear()
        self._system_line("Conversation cleared.")

    # --- worker plumbing -------------------------------------------------
    # Completions are dispatched through self-bound slots so they run on the
    # GUI thread (a plain closure would run on the worker thread and deadlock
    # on thread.wait()). Each job carries a generation so Stop can discard the
    # result of an in-flight request.
    def _run(self, fn, on_done, on_fail) -> None:
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        self._jobs[id(worker)] = (thread, worker, on_done, on_fail, self._gen)
        thread.started.connect(worker.run)
        worker.done.connect(self._job_done)
        worker.failed.connect(self._job_failed)
        self._threads.append(thread)
        thread.start()

    def _finish_job(self, worker):
        job = self._jobs.pop(id(worker), None)
        if job is not None:
            thread = job[0]
            thread.quit()
            thread.wait()
            if thread in self._threads:
                self._threads.remove(thread)
        return job

    def _job_done(self, result) -> None:
        job = self._finish_job(self.sender())
        if job is not None and job[4] == self._gen:
            job[2](result)  # on_done

    def _job_failed(self, msg) -> None:
        job = self._finish_job(self.sender())
        if job is not None and job[4] == self._gen:
            job[3](msg)  # on_fail

    def _stop(self) -> None:
        """Cancel the in-flight request; its result will be discarded."""
        if not self._busy and self.refresh_btn.isEnabled():
            return
        self._gen += 1
        self._set_busy(False)
        self.refresh_btn.setEnabled(True)
        self._system_line("Request cancelled.")

    def stop(self) -> None:
        self._gen += 1
        for thread in list(self._threads):
            thread.quit()
            thread.wait()
        self._threads.clear()
        self._jobs.clear()

    # --- rendering -------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.send_btn.setEnabled(not busy)
        self.send_btn.setText("…" if busy else "Send")
        self.stop_btn.setEnabled(busy)
        self.input.setReadOnly(busy)

    def _append(self, role: str, text: str) -> None:
        who = "You" if role == "user" else ai.PROVIDERS[self._provider()]["label"]
        color = "#58A6FF" if role == "user" else "#3FB950"
        safe = html.escape(text)
        self.view.append(
            f'<p style="margin:8px 0 2px 0"><b style="color:{color}">{who}</b></p>'
        )
        self.view.append(
            f'<pre style="white-space:pre-wrap;margin:0;font-family:Consolas,'
            f'monospace">{safe}</pre>'
        )
        self.view.verticalScrollBar().setValue(
            self.view.verticalScrollBar().maximum())

    def _system_line(self, text: str) -> None:
        self.view.append(
            f'<p style="margin:6px 0;color:#8B949E"><i>{html.escape(text)}</i></p>'
        )

    # --- key management / help -------------------------------------------
    def _need_key(self, provider: str) -> None:
        QMessageBox.information(
            self, "API key needed",
            f"{ai.PROVIDERS[provider]['label']} needs an API key.\n\n"
            f"{ai.PROVIDERS[provider]['key_help']}",
        )
        self.open_keys()

    def open_keys(self) -> None:
        AIKeysDialog(self.settings, self).exec()

    def show_help(self) -> None:
        lines = ["<b>Getting an API key</b><br>"]
        for pid in ai.PROVIDER_ORDER:
            meta = ai.PROVIDERS[pid]
            lines.append(
                f"<p><b>{html.escape(meta['label'])}</b><br>"
                f"{html.escape(meta['key_help'])}<br>"
                f"<a href='{meta['key_url']}'>{meta['key_url']}</a></p>"
            )
        box = QMessageBox(self)
        box.setWindowTitle("How to get an API key")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText("".join(lines))
        box.exec()
