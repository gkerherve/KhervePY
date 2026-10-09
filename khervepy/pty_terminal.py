"""A real terminal for macOS and Linux: a pseudo-terminal plus a VT emulator.

``terminal.py`` is a line-oriented pipe, which is fine for ``ls`` and ``git``
but not for anything that wants a TTY — ``claude``, ``python -i``, ``vim``,
``htop``, colours, job control, Ctrl-C. This module runs the shell on a real
PTY and draws it with `pyte <https://github.com/selectel/pyte>`_ (a pure-Python
VT100/xterm emulator), so those programs behave as they do in Terminal.app.

Pieces, bottom to top:

* ``_Screen`` — ``pyte.HistoryScreen`` plus the alternate screen buffer
  (``ESC[?1049h``), which full-screen programs use and pyte ignores.
* ``_TerminalView`` — a ``QAbstractScrollArea`` that owns the PTY, feeds the
  emulator and paints its cells (colours, bold, underline, cursor, selection,
  scrollback).
* ``PtyTerminal`` — the dock widget: the view plus Clear / Restart, with the
  same public surface as the Windows pipe terminal (``view``, ``cwd``,
  ``start``, ``restart``, ``stop``, ``set_cwd``, ``send_command``).

macOS note: Qt swaps the keys — ``ControlModifier`` is **Cmd** and
``MetaModifier`` is the physical **Ctrl**. So Cmd+C copies, Cmd+V pastes, and a
real Ctrl+C sends the interrupt, exactly as in Terminal.app.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy
import fcntl
import os
import pty
import signal
import struct
import subprocess
import sys
import termios

import pyte
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSocketNotifier, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QPainter,
)
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_IS_MAC = sys.platform == "darwin"
_HISTORY = 5000
_ALT_SCREEN_MODES = (47, 1047, 1049)
_BRACKETED_PASTE = 2004 << 5          # pyte stores private modes shifted by 5

# 16 ANSI colours for a dark and for a light background.
_ANSI_DARK = {
    "black": "#555a63", "red": "#e06c75", "green": "#98c379", "brown": "#e5c07b",
    "blue": "#61afef", "magenta": "#c678dd", "cyan": "#56b6c2", "white": "#dcdfe4",
    "brightblack": "#7f848e", "brightred": "#ff7b86", "brightgreen": "#b1e08a",
    "brightbrown": "#f2d28b", "brightblue": "#7dc1ff", "brightmagenta": "#dd8cf5",
    "brightcyan": "#6fd0dc", "brightwhite": "#ffffff",
}
_ANSI_LIGHT = {
    "black": "#24292f", "red": "#cf222e", "green": "#116329", "brown": "#9a6700",
    "blue": "#0969da", "magenta": "#8250df", "cyan": "#1b7c83", "white": "#6e7781",
    "brightblack": "#57606a", "brightred": "#a40e26", "brightgreen": "#1a7f37",
    "brightbrown": "#7d4e00", "brightblue": "#218bff", "brightmagenta": "#a475f9",
    "brightcyan": "#3192aa", "brightwhite": "#8c959f",
}


class _Screen(pyte.HistoryScreen):
    """HistoryScreen + alternate screen + replies to terminal queries."""

    def __init__(self, columns: int, lines: int, on_reply):
        super().__init__(columns, lines, history=_HISTORY, ratio=0.5)
        self._reply = on_reply
        self._main = None          # saved (buffer, cursor) while on the alt screen

    @property
    def on_alt_screen(self) -> bool:
        return self._main is not None

    # pyte asks the host to answer device-status / attribute queries.
    def write_process_input(self, data: str) -> None:
        self._reply(data.encode())

    def index(self) -> None:
        if self.on_alt_screen:     # a full-screen app's scroll is not history
            pyte.Screen.index(self)
        else:
            super().index()

    def set_mode(self, *modes, **kwargs) -> None:
        if kwargs.get("private") and any(m in _ALT_SCREEN_MODES for m in modes):
            self._enter_alt()
            modes = tuple(m for m in modes if m not in _ALT_SCREEN_MODES)
        if modes:
            super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes, **kwargs) -> None:
        if kwargs.get("private") and any(m in _ALT_SCREEN_MODES for m in modes):
            self._leave_alt()
            modes = tuple(m for m in modes if m not in _ALT_SCREEN_MODES)
        if modes:
            super().reset_mode(*modes, **kwargs)

    def _enter_alt(self) -> None:
        if self._main is not None:
            return
        self._main = (copy.deepcopy(self.buffer), copy.copy(self.cursor))
        self.erase_in_display(2)
        self.cursor_position()

    def _leave_alt(self) -> None:
        if self._main is None:
            return
        self.buffer, self.cursor = self._main
        self._main = None
        self.dirty.update(range(self.lines))


class _TerminalView(QAbstractScrollArea):
    """Owns the PTY and the emulator, and paints the result."""

    def __init__(self, cwd: str, parent=None):
        super().__init__(parent)
        self.cwd = cwd
        self._proc: subprocess.Popen | None = None
        self._master = -1
        self._notifier: QSocketNotifier | None = None
        self._exited = False
        self._follow = True
        self._sel: tuple[tuple[int, int], tuple[int, int]] | None = None
        self._dragging = False
        self._theme = None

        self._screen = _Screen(80, 24, self._write)
        self._stream = pyte.ByteStream(self._screen)

        from khervepy.fonts import mono_font
        self.setFont(mono_font(12 if _IS_MAC else 10))

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._fg = QColor("#d4d4d4")
        self._bg = QColor("#1e1e1e")
        self._sel_bg = QColor("#264f78")
        self._ansi = _ANSI_DARK
        self._measure()

        self._poll = QTimer(self)
        self._poll.setInterval(400)
        self._poll.timeout.connect(self._check_exit)

    # --- theme / metrics -----------------------------------------------------
    def apply_theme(self, theme) -> None:
        self._theme = theme
        self._bg = QColor(theme.background)
        self._fg = QColor(theme.foreground)
        self._sel_bg = QColor(theme.selection_bg)
        self._ansi = _ANSI_DARK if self._bg.lightness() < 128 else _ANSI_LIGHT
        self.viewport().update()

    def _measure(self) -> None:
        # Floats: Menlo's cell is 9.625 px wide. Rounding it to 9 makes a long
        # run of text (drawn with the font's own advance) drift off the grid
        # and collide with the next run.
        metrics = QFontMetricsF(self.font())
        self._cw = max(1.0, metrics.horizontalAdvance("M"))
        self._ch = max(1, math.ceil(metrics.height()))
        self._ascent = metrics.ascent()

    def _colour(self, name: str, default: QColor) -> QColor:
        if name == "default":
            return default
        if name in self._ansi:
            return QColor(self._ansi[name])
        if len(name) == 6:
            return QColor(f"#{name}")
        return default

    # --- process ---------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def shell_is_foreground(self) -> bool:
        """True when the shell, not a program it started, owns the terminal."""
        if not self.running or self._master < 0:
            return False
        try:
            return os.tcgetpgrp(self._master) == self._proc.pid
        except OSError:
            return False

    def _shell_command(self) -> list[str]:
        shell = os.environ.get("SHELL") or "/bin/zsh"
        if not os.path.isfile(shell):
            shell = "/bin/sh"
        # A login shell, so ~/.zprofile / ~/.bash_profile put Homebrew and the
        # user's Pythons on PATH even when KhervePY was started from Finder.
        return [shell, "-l"]

    def _environment(self) -> dict:
        env = dict(os.environ)
        env.update(TERM="xterm-256color", COLORTERM="truecolor",
                   TERM_PROGRAM="KhervePY")
        env.setdefault("LANG", "en_US.UTF-8")
        env.setdefault("LC_CTYPE", "UTF-8")
        # PyInstaller points the loader at the bundle; a child must not.
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env.pop("LD_LIBRARY_PATH_ORIG")
        for key in ("PYTHONHOME", "PYTHONPATH", "_MEIPASS2"):
            env.pop(key, None)
        try:
            from khervepy import __version__
            env["TERM_PROGRAM_VERSION"] = __version__
        except ImportError:
            pass
        return env

    def start(self) -> None:
        if self.running:
            return
        self._exited = False
        rows, cols = self._grid()
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        cwd = self.cwd if os.path.isdir(self.cwd) else os.path.expanduser("~")
        try:
            self._proc = subprocess.Popen(
                self._shell_command(), stdin=slave, stdout=slave, stderr=slave,
                cwd=cwd, env=self._environment(), close_fds=True,
                start_new_session=True,
                # setsid has run by now: make the PTY this session's terminal,
                # which is what lets Ctrl-C, Ctrl-Z and job control work.
                preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),
            )
        except OSError as exc:
            os.close(master)
            os.close(slave)
            self._feed(f"\r\n[could not start the shell: {exc}]\r\n".encode())
            return
        os.close(slave)
        self._master = master
        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._notifier = QSocketNotifier(master, QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._on_readable)
        self._poll.start()

    def stop(self) -> None:
        self._poll.stop()
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier.deleteLater()
            self._notifier = None
        proc, self._proc = self._proc, None
        # Close our end of the PTY *first*. That hangs the terminal up (SIGHUP to
        # the shell's session) and, just as important, lets a shell that is mid-
        # exit finish: while it is blocked flushing output into a PTY nobody
        # reads, macOS reports it as "exiting" and even refuses to signal it.
        if self._master >= 0:
            try:
                os.close(self._master)
            except OSError:
                pass
            self._master = -1
        if proc is not None and proc.poll() is None:
            for sig, wait in ((signal.SIGHUP, 1.0), (signal.SIGKILL, 2.0)):
                try:
                    os.killpg(proc.pid, sig)
                except OSError:
                    pass
                try:
                    proc.wait(timeout=wait)
                    break
                except subprocess.TimeoutExpired:
                    continue

    def restart(self) -> None:
        self.stop()
        self._reset_screen()
        self.start()

    def clear_all(self) -> None:
        """Clear the scrollback and the visible screen (the shell redraws its prompt)."""
        self._screen.history.top.clear()
        self._screen.erase_in_display(2)
        self._screen.cursor_position()
        self._sel = None
        self._after_output()
        if self.shell_is_foreground():
            self._write(b"\x0c")                     # Ctrl-L: redraw the prompt

    def _reset_screen(self) -> None:
        rows, cols = self._grid()
        self._screen = _Screen(cols, rows, self._write)
        self._stream = pyte.ByteStream(self._screen)
        self._sel = None
        self._follow = True
        self._after_output()

    # --- io --------------------------------------------------------------------
    def _write(self, data: bytes) -> None:
        if self._master < 0:
            return
        try:
            os.write(self._master, data)
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            pass

    def _on_readable(self) -> None:
        try:
            data = os.read(self._master, 1 << 16)
        except BlockingIOError:
            return
        except OSError:                               # EIO: the shell is gone
            self._check_exit(force=True)
            return
        if not data:
            self._check_exit(force=True)
            return
        self._feed(data)

    def _feed(self, data: bytes) -> None:
        self._stream.feed(data)
        self._after_output()

    def _check_exit(self, force: bool = False) -> None:
        proc = self._proc
        if proc is None or self._exited:
            return
        code = proc.poll()
        if code is None and force:
            try:
                code = proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                return
        if code is None:
            return
        self._exited = True
        self._poll.stop()
        if self._notifier is not None:
            self._notifier.setEnabled(False)
        self._feed(f"\r\n[shell exited with code {code} — press any key to restart]\r\n"
                   .encode())

    def send_text(self, text: str) -> None:
        self._write(text.encode("utf-8"))

    # --- geometry --------------------------------------------------------------
    def _grid(self) -> tuple[int, int]:
        vp = self.viewport()
        cols = max(20, int(vp.width() // self._cw))
        rows = max(5, int(vp.height() // self._ch))
        return rows, cols

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        rows, cols = self._grid()
        if (rows, cols) != (self._screen.lines, self._screen.columns):
            self._screen.resize(rows, cols)
            if self._master >= 0:
                try:
                    fcntl.ioctl(self._master, termios.TIOCSWINSZ,
                                struct.pack("HHHH", rows, cols, 0, 0))
                except OSError:
                    pass
        self._update_scrollbar()

    # --- scrolling -------------------------------------------------------------
    def _history_len(self) -> int:
        return 0 if self._screen.on_alt_screen else len(self._screen.history.top)

    def _update_scrollbar(self) -> None:
        bar = self.verticalScrollBar()
        bar.blockSignals(True)
        top = self._history_len()
        bar.setRange(0, top)
        bar.setPageStep(self._screen.lines)
        bar.setValue(top if self._follow else min(bar.value(), top))
        bar.blockSignals(False)

    def _on_scroll(self, value: int) -> None:
        self._follow = value >= self.verticalScrollBar().maximum()
        self.viewport().update()

    def _after_output(self) -> None:
        self._update_scrollbar()
        self.viewport().update()

    def _scroll_to_bottom(self) -> None:
        self._follow = True
        self._update_scrollbar()
        self.viewport().update()

    # --- painting --------------------------------------------------------------
    def _line(self, absolute: int):
        """Combined index: scrollback lines first, then the live screen."""
        hist = self._screen.history.top if not self._screen.on_alt_screen else ()
        if absolute < len(hist):
            return hist[absolute]
        return self._screen.buffer[absolute - len(hist)]

    def _first_visible(self) -> int:
        return self.verticalScrollBar().value() if not self._follow else self._history_len()

    def paintEvent(self, event) -> None:
        p = QPainter(self.viewport())
        p.setFont(self.font())
        p.fillRect(self.viewport().rect(), self._bg)
        screen = self._screen
        first = self._first_visible()
        bold_font = QFont(self.font())
        bold_font.setBold(True)
        sel = self._normalised_selection()

        for row in range(screen.lines):
            absolute = first + row
            if absolute >= self._history_len() + screen.lines:
                break
            line = self._line(absolute)
            y = row * self._ch
            col = 0
            while col < screen.columns:
                ch = line[col]
                key = (ch.fg, ch.bg, ch.bold, ch.italics, ch.underscore,
                       ch.strikethrough, ch.reverse)
                end = col + 1
                text = ch.data or " "
                while end < screen.columns:
                    nxt = line[end]
                    if (nxt.fg, nxt.bg, nxt.bold, nxt.italics, nxt.underscore,
                            nxt.strikethrough, nxt.reverse) != key:
                        break
                    text += nxt.data or ""
                    end += 1
                self._paint_run(p, bold_font, y, col, end, text, key, sel, absolute)
                col = end

        if (not self._screen.cursor.hidden and self._follow):
            cx = screen.cursor.x * self._cw
            cy = screen.cursor.y * self._ch
            if self.hasFocus():
                p.fillRect(QRectF(cx, cy, self._cw, self._ch), self._fg)
                under = screen.buffer[screen.cursor.y][screen.cursor.x].data or " "
                p.setPen(self._bg)
                p.drawText(QPointF(cx, cy + self._ascent), under)
            else:
                p.setPen(self._fg)
                p.drawRect(QRectF(cx, cy, self._cw - 1, self._ch - 1))
        p.end()

    def _paint_run(self, p, bold_font, y, c0, c1, text, key, sel, absolute) -> None:
        fg, bg, bold, italics, underscore, strike, reverse = key
        fg_c = self._colour(fg, self._fg)
        bg_c = self._colour(bg, self._bg)
        if reverse:
            fg_c, bg_c = bg_c, fg_c
        x = c0 * self._cw
        width = (c1 - c0) * self._cw
        if bg_c != self._bg or reverse:
            p.fillRect(QRectF(x, y, width, self._ch), bg_c)
        if sel is not None:                           # selection highlight
            (sl, sc), (el, ec) = sel
            if sl <= absolute <= el:
                lo = sc if absolute == sl else 0
                hi = ec if absolute == el else self._screen.columns
                a, b = max(lo, c0), min(hi, c1)
                if a < b:
                    p.fillRect(QRectF(a * self._cw, y, (b - a) * self._cw, self._ch),
                               self._sel_bg)
        font = bold_font if bold else self.font()
        if italics or font.italic() != italics:
            font = QFont(font)
            font.setItalic(bool(italics))
        p.setFont(font)
        p.setPen(fg_c)
        base = y + self._ascent
        if text.isascii():
            p.drawText(QPointF(x, base), text)
        else:                                         # keep wide glyphs on the grid
            col = c0
            for ch in text:
                p.drawText(QPointF(col * self._cw, base), ch)
                col += 1
        if underscore:
            p.drawLine(QPointF(x, y + self._ch - 2), QPointF(x + width, y + self._ch - 2))
        if strike:
            p.drawLine(QPointF(x, y + self._ch / 2), QPointF(x + width, y + self._ch / 2))

    # --- selection / clipboard ---------------------------------------------------
    def _cell_at(self, pos) -> tuple[int, int]:
        row = max(0, min(self._screen.lines - 1, int(pos.y() // self._ch)))
        col = max(0, min(self._screen.columns, int(pos.x() // self._cw)))
        return self._first_visible() + row, col

    def _normalised_selection(self):
        if self._sel is None:
            return None
        a, b = self._sel
        return (a, b) if a <= b else (b, a)

    def selected_text(self) -> str:
        sel = self._normalised_selection()
        if sel is None or sel[0] == sel[1]:
            return ""
        (sl, sc), (el, ec) = sel
        out = []
        for absolute in range(sl, el + 1):
            line = self._line(absolute)
            lo = sc if absolute == sl else 0
            hi = ec if absolute == el else self._screen.columns
            out.append("".join(line[c].data or " " for c in range(lo, hi)).rstrip())
        return "\n".join(out)

    def copy(self) -> bool:
        text = self.selected_text()
        if text:
            QGuiApplication.clipboard().setText(text)
        return bool(text)

    def paste(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        text = text.replace("\r\n", "\n").replace("\n", "\r")
        if _BRACKETED_PASTE in self._screen.mode:
            text = "\x1b[200~" + text + "\x1b[201~"
        self.send_text(text)
        self._scroll_to_bottom()

    def mousePressEvent(self, event) -> None:
        self.setFocus()
        if event.button() == Qt.MouseButton.LeftButton:
            cell = self._cell_at(event.position().toPoint())
            self._sel = (cell, cell)
            self._dragging = True
            self.viewport().update()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and self._sel is not None:
            self._sel = (self._sel[0], self._cell_at(event.position().toPoint()))
            self.viewport().update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            if self._sel is not None and self._sel[0] == self._sel[1]:
                self._sel = None
                self.viewport().update()

    def mouseDoubleClickEvent(self, event) -> None:
        absolute, col = self._cell_at(event.position().toPoint())
        line = self._line(absolute)
        n = self._screen.columns

        def word(c):
            d = line[c].data
            return bool(d) and (d.isalnum() or d in "_-./~")
        if col < n and word(col):
            lo = hi = col
            while lo > 0 and word(lo - 1):
                lo -= 1
            while hi < n and word(hi):
                hi += 1
            self._sel = ((absolute, lo), (absolute, hi))
            self.viewport().update()

    # --- keyboard ----------------------------------------------------------------
    def focusNextPrevChild(self, _forward: bool) -> bool:
        return False                                  # Tab belongs to the shell

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.viewport().update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.viewport().update()

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.ShortcutOverride and self._wants_key(event):
            event.accept()                            # the terminal, not a menu, gets it
            return True
        return super().event(event)

    def _wants_key(self, event) -> bool:
        mods = event.modifiers()
        key = event.key()
        ctrl = Qt.KeyboardModifier.ControlModifier
        meta = Qt.KeyboardModifier.MetaModifier
        if _IS_MAC:
            if mods & ctrl:                           # Cmd: only our own few
                return key in (Qt.Key.Key_C, Qt.Key.Key_V, Qt.Key.Key_K,
                               Qt.Key.Key_Left, Qt.Key.Key_Right,
                               Qt.Key.Key_Backspace)
            return True
        if mods & ctrl and key == Qt.Key.Key_QuoteLeft:
            return False                              # Ctrl+` toggles the dock
        return True

    _FKEYS = {Qt.Key.Key_F1: "OP", Qt.Key.Key_F2: "OQ", Qt.Key.Key_F3: "OR",
              Qt.Key.Key_F4: "OS", Qt.Key.Key_F5: "[15~", Qt.Key.Key_F6: "[17~",
              Qt.Key.Key_F7: "[18~", Qt.Key.Key_F8: "[19~", Qt.Key.Key_F9: "[20~",
              Qt.Key.Key_F10: "[21~", Qt.Key.Key_F11: "[23~", Qt.Key.Key_F12: "[24~"}

    def keyPressEvent(self, event) -> None:
        if self._exited:
            self.restart()
            return
        mods = event.modifiers()
        key = event.key()
        ctrl = Qt.KeyboardModifier.ControlModifier
        shift = Qt.KeyboardModifier.ShiftModifier
        alt = Qt.KeyboardModifier.AltModifier
        meta = Qt.KeyboardModifier.MetaModifier
        text = event.text()

        # --- copy / paste / clear -------------------------------------------------
        if _IS_MAC:
            if mods & ctrl:                           # Cmd
                if key == Qt.Key.Key_C:
                    self.copy()
                elif key == Qt.Key.Key_V:
                    self.paste()
                elif key == Qt.Key.Key_K:
                    self.clear_all()
                elif key == Qt.Key.Key_Left:
                    self.send_text("\x01")            # line start
                elif key == Qt.Key.Key_Right:
                    self.send_text("\x05")            # line end
                elif key == Qt.Key.Key_Backspace:
                    self.send_text("\x15")            # kill line
                return
            real_ctrl = bool(mods & meta)
        else:
            real_ctrl = bool(mods & ctrl)
            if real_ctrl and mods & shift:
                if key == Qt.Key.Key_C:
                    self.copy()
                    return
                if key == Qt.Key.Key_V:
                    self.paste()
                    return

        # --- scrollback with Shift+PageUp/Down ------------------------------------
        bar = self.verticalScrollBar()
        if mods & shift and key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            step = bar.pageStep() - 1
            bar.setValue(bar.value() + (-step if key == Qt.Key.Key_PageUp else step))
            return

        data = self._encode(key, text, mods, real_ctrl, bool(mods & alt))
        if data is None:
            return
        self._sel = None
        self._scroll_to_bottom()
        self._write(data)

    def _encode(self, key, text, mods, real_ctrl: bool, alt: bool) -> bytes | None:
        app_keys = (1 << 5) in self._screen.mode      # DECCKM: application cursor keys
        arrows = {Qt.Key.Key_Up: "A", Qt.Key.Key_Down: "B",
                  Qt.Key.Key_Right: "C", Qt.Key.Key_Left: "D",
                  Qt.Key.Key_Home: "H", Qt.Key.Key_End: "F"}
        if key in arrows:
            letter = arrows[key]
            if alt and key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                return b"\x1bb" if key == Qt.Key.Key_Left else b"\x1bf"   # by word
            if mods & Qt.KeyboardModifier.ShiftModifier or real_ctrl:
                return f"\x1b[1;{'2' if not real_ctrl else '5'}{letter}".encode()
            return (f"\x1bO{letter}" if app_keys else f"\x1b[{letter}").encode()
        simple = {
            Qt.Key.Key_Return: b"\r", Qt.Key.Key_Enter: b"\r",
            Qt.Key.Key_Backspace: b"\x7f", Qt.Key.Key_Tab: b"\t",
            Qt.Key.Key_Backtab: b"\x1b[Z", Qt.Key.Key_Escape: b"\x1b",
            Qt.Key.Key_Delete: b"\x1b[3~", Qt.Key.Key_Insert: b"\x1b[2~",
            Qt.Key.Key_PageUp: b"\x1b[5~", Qt.Key.Key_PageDown: b"\x1b[6~",
        }
        if key in simple:
            data = simple[key]
            return b"\x1b" + data if alt and key == Qt.Key.Key_Backspace else data
        if key in self._FKEYS:
            return ("\x1b" + self._FKEYS[key]).encode()

        if real_ctrl and Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return bytes([key - Qt.Key.Key_A + 1])
        if real_ctrl and key == Qt.Key.Key_Space:
            return b"\x00"
        if real_ctrl and key == Qt.Key.Key_BracketLeft:
            return b"\x1b"
        if real_ctrl and key == Qt.Key.Key_Backslash:
            return b"\x1c"
        if real_ctrl and key == Qt.Key.Key_BracketRight:
            return b"\x1d"
        if text and text.isprintable():
            data = text.encode("utf-8")
            return b"\x1b" + data if alt and not _IS_MAC else data
        if text and text in ("\x1b",):
            return text.encode()
        return None

    def inputMethodEvent(self, event) -> None:        # CJK / dead-key composition
        committed = event.commitString()
        if committed:
            self._scroll_to_bottom()
            self.send_text(committed)

    def keyReleaseEvent(self, event) -> None:
        event.accept()


class PtyTerminal(QWidget):
    """Persistent shell on a real PTY, in a dockable widget."""

    def __init__(self, cwd: str | None = None, parent=None):
        super().__init__(parent)
        self.view = _TerminalView(cwd or os.getcwd())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        layout.addWidget(self.view, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.view.clear_all)
        restart_btn = QPushButton("Restart")
        restart_btn.clicked.connect(self.restart)
        row.addWidget(clear_btn)
        row.addWidget(restart_btn)
        layout.addLayout(row)

        self.setFocusProxy(self.view)
        self.view.start()

    # --- the surface main_window uses ---------------------------------------------
    @property
    def cwd(self) -> str:
        return self.view.cwd

    def start(self) -> None:
        self.view.start()

    def restart(self) -> None:
        self.view.restart()

    def stop(self) -> None:
        self.view.stop()

    def apply_theme(self, theme) -> None:
        self.view.apply_theme(theme)

    def set_cwd(self, path: str) -> None:
        """Follow the active project.

        Only types ``cd`` when the shell is waiting at its prompt: while a
        program is running (``claude``, ``python -i``, a build) the keystrokes
        would land in *that program*, so the new folder is remembered and used
        the next time the shell starts.
        """
        self.view.cwd = path
        if not self.view.running:
            self.view.restart()
        elif self.view.shell_is_foreground():
            quoted = "'" + path.replace("'", "'\\''") + "'"
            self.view.send_text(f"\x15cd {quoted} && clear\r")   # ^U drops half-typed text

    def send_command(self, text: str, echo: bool = False) -> None:
        """Type ``text`` and Enter into the shell (the shell does the echoing)."""
        if not self.view.running:
            self.view.start()
        self.view.send_text(text + "\r")

    def hasFocusInside(self) -> bool:
        return self.view.hasFocus()
