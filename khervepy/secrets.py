"""Secrets (GitHub token, AI API keys) in the operating system's keychain.

macOS Keychain, Windows Credential Locker or the Secret Service on Linux,
through the ``keyring`` package — instead of a plain preferences file that any
backup or cloud-sync of ``~/Library/Preferences`` would copy around.

Every call degrades safely: if ``keyring`` is missing, has no usable backend,
or the user declines the keychain prompt, ``get`` returns ``None`` and ``set``
returns ``False``, and ``Settings`` keeps the value where it always was. Set
``KHERVEPY_NO_KEYRING=1`` to skip the keychain entirely (CI, the self-test).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

SERVICE = "KhervePY"
_cache: dict[str, str] = {}
_unavailable = False


def _keyring():
    global _unavailable
    if _unavailable or os.environ.get("KHERVEPY_NO_KEYRING"):
        return None
    try:
        import keyring
        from keyring.backends import fail
        if isinstance(keyring.get_keyring(), fail.Keyring):
            _unavailable = True
            return None
        return keyring
    except Exception:
        _unavailable = True
        return None


def available() -> bool:
    return _keyring() is not None


def get(name: str) -> str | None:
    """The stored secret, ``""`` if the keychain has none, ``None`` if unusable."""
    if name in _cache:
        return _cache[name]
    kr = _keyring()
    if kr is None:
        return None
    try:
        value = kr.get_password(SERVICE, name) or ""
    except Exception:
        return None
    _cache[name] = value
    return value


def set(name: str, value: str) -> bool:  # noqa: A001  (mirrors keyring's own verb)
    kr = _keyring()
    if kr is None:
        return False
    try:
        if value:
            kr.set_password(SERVICE, name, value)
        else:
            try:
                kr.delete_password(SERVICE, name)
            except Exception:
                pass                      # nothing stored: already what was asked
    except Exception:
        return False
    _cache[name] = value
    return True
