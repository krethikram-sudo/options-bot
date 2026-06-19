"""At-rest encryption for stored secrets (connector tokens).

Tokens are encrypted with Fernet using a key derived from CONSOLE_SECRET, so a
leak of the SQLite file alone doesn't expose customers' API keys. Values are
prefixed `enc:` so decryption is unambiguous and pre-existing plaintext rows
stay readable (migrated on next save).

Degrades gracefully: if `cryptography` isn't installed (dev), values are stored
as-is — set CONSOLE_SECRET and install cryptography in any real deployment.
console/requirements.txt pins it, so production and CI always encrypt.
"""

from __future__ import annotations

import base64
import hashlib
import os

try:  # optional dependency — present in requirements, may be absent in bare dev
    from cryptography.fernet import Fernet, InvalidToken
    _HAVE = True
except Exception:  # noqa: BLE001
    _HAVE = False

PREFIX = "enc:"


def available() -> bool:
    return _HAVE


def _key() -> bytes:
    sec = os.environ.get("CONSOLE_SECRET") or "dev-insecure-console-secret"
    return base64.urlsafe_b64encode(hashlib.sha256(sec.encode()).digest())


def encrypt(value: str | None) -> str | None:
    """Encrypt a secret for storage. No-op on empty values or without the lib."""
    if not value or not _HAVE:
        return value
    return PREFIX + Fernet(_key()).encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    """Decrypt a stored secret. Pass through plaintext (pre-encryption) values."""
    if not value or not value.startswith(PREFIX):
        return value
    if not _HAVE:
        return value
    try:
        return Fernet(_key()).decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        return value
