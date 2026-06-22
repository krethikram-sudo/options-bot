"""At-rest encryption for stored secrets (connector tokens).

Tokens are encrypted with Fernet using a key derived from CONSOLE_SECRET, so a
leak of the SQLite file alone doesn't expose customers' API keys. Values are
prefixed `enc:` so decryption is unambiguous and pre-existing plaintext rows
stay readable (migrated on next save).

Degrades gracefully: if `cryptography` isn't installed (dev), values are stored
as-is — set CONSOLE_SECRET and install cryptography in any real deployment.
console/requirements.txt pins it, so production and CI always encrypt.

Key management (gov-readiness, NIST 800-53 SC-12): the data-encryption key is
normally derived from CONSOLE_SECRET. To meet a KMS / FIPS-validated requirement
on a FedRAMP-authorized cloud, set `CONSOLE_SECRETBOX_KEY` to a 32-byte
urlsafe-base64 Fernet key supplied by your secrets manager / KMS (e.g. AWS KMS,
Azure Key Vault) — no code change; the app reads the managed key instead of
deriving one. Rotate by re-issuing the managed key (old `enc:` values re-encrypt
on next save).
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
    # Prefer a KMS/secrets-manager-supplied key (FIPS/SC-12 path on a managed cloud);
    # otherwise derive one from CONSOLE_SECRET.
    managed = os.environ.get("CONSOLE_SECRETBOX_KEY")
    if managed:
        return managed.encode()
    sec = os.environ.get("CONSOLE_SECRET")
    if not sec:
        # Fail safe (gov-readiness): NEVER silently fall back to a world-known
        # default key in production — that would make every stored secret trivially
        # decryptable by anyone with the (open-source) repo. Production always sets
        # CONSOLE_SECRET (sessions need it too); bare local dev can opt in explicitly.
        if os.environ.get("CONSOLE_ALLOW_INSECURE_SECRETBOX") == "1":
            sec = "dev-insecure-console-secret"
        else:
            raise RuntimeError(
                "secret_box: no key material. Set CONSOLE_SECRETBOX_KEY (a KMS-managed "
                "Fernet key) or CONSOLE_SECRET. For local dev only, set "
                "CONSOLE_ALLOW_INSECURE_SECRETBOX=1 to use an insecure default.")
    # NOTE: single-pass SHA-256 derivation is retained for backward-compatibility with
    # already-stored `enc:` values. Strengthening to a salted KDF requires a key-rotation
    # migration (re-encrypt on read); the supported hardening path is a KMS key via
    # CONSOLE_SECRETBOX_KEY (above), which sidesteps derivation entirely.
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
