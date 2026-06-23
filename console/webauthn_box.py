"""WebAuthn / passkeys (FIDO2) — phishing-resistant MFA on top of TOTP.

Thin wrapper around the vetted `py_webauthn` library (we never hand-roll the
attestation/assertion crypto). Degrades gracefully: if `webauthn` isn't installed
the console still runs and passkey features report unavailable — exactly like
`secret_box` degrades without `cryptography`. `console/requirements.txt` pins it,
so production and CI always have it.

Relying-Party config (must match the browser's origin or the ceremony fails):
  CONSOLE_RP_ID    — the RP ID (an effective domain, e.g. "console.outlay-ai.com").
                     Defaults to the host of CONSOLE_BASE_URL, else "localhost".
  CONSOLE_BASE_URL — the full origin (scheme://host[:port]) the app is served from.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlsplit

try:  # optional dependency — present in requirements, may be absent in bare dev
    from webauthn import (generate_registration_options, verify_registration_response,
                          generate_authentication_options, verify_authentication_response,
                          options_to_json)
    from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
    from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, ResidentKeyRequirement,
                                          UserVerificationRequirement, PublicKeyCredentialDescriptor)
    _HAVE = True
except Exception:  # noqa: BLE001
    _HAVE = False


def available() -> bool:
    return _HAVE


def rp_id() -> str:
    explicit = os.environ.get("CONSOLE_RP_ID")
    if explicit:
        return explicit.strip()
    host = urlsplit(os.environ.get("CONSOLE_BASE_URL", "")).hostname
    return host or "localhost"


def origin() -> str:
    base = os.environ.get("CONSOLE_BASE_URL")
    if base:
        return base.rstrip("/")
    return "http://localhost"


def _name() -> str:
    return os.environ.get("CONSOLE_RP_NAME", "Outlay")


# --- Registration (enroll a new passkey) ----------------------------------- #

def registration_options(user_handle: bytes, user_name: str,
                         existing_credential_ids: list[bytes] | None = None) -> tuple[str, str]:
    """Return (options_json_for_the_browser, challenge_b64url_to_stash_server-side)."""
    opts = generate_registration_options(
        rp_id=rp_id(), rp_name=_name(), user_id=user_handle, user_name=user_name,
        user_display_name=user_name,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=c) for c in (existing_credential_ids or [])],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED),
    )
    return options_to_json(opts), bytes_to_base64url(opts.challenge)


def verify_registration(credential_json: str, challenge_b64: str) -> dict:
    """Verify the browser's attestation. Returns the stored credential material."""
    reg = verify_registration_response(
        credential=credential_json, expected_challenge=base64url_to_bytes(challenge_b64),
        expected_rp_id=rp_id(), expected_origin=origin())
    return {"credential_id": bytes_to_base64url(reg.credential_id),
            "public_key": bytes_to_base64url(reg.credential_public_key),
            "sign_count": reg.sign_count}


# --- Authentication (sign in with a passkey) ------------------------------- #

def authentication_options(credential_ids: list[bytes]) -> tuple[str, str]:
    """Return (options_json_for_the_browser, challenge_b64url_to_stash)."""
    opts = generate_authentication_options(
        rp_id=rp_id(),
        allow_credentials=[PublicKeyCredentialDescriptor(id=c) for c in credential_ids],
        user_verification=UserVerificationRequirement.PREFERRED)
    return options_to_json(opts), bytes_to_base64url(opts.challenge)


def verify_authentication(credential_json: str, challenge_b64: str, public_key_b64: str,
                          current_sign_count: int) -> int:
    """Verify the browser's assertion against a stored public key. Returns the new
    signature counter (caller must persist it; a counter that doesn't advance is a
    cloned-authenticator signal — py_webauthn raises if it regresses)."""
    res = verify_authentication_response(
        credential=credential_json, expected_challenge=base64url_to_bytes(challenge_b64),
        expected_rp_id=rp_id(), expected_origin=origin(),
        credential_public_key=base64url_to_bytes(public_key_b64),
        credential_current_sign_count=current_sign_count)
    return res.new_sign_count


def credential_id_of(credential_json: str) -> str:
    """The base64url credential id the browser is asserting (to look up the stored key)."""
    raw = json.loads(credential_json).get("rawId") or json.loads(credential_json).get("id")
    return raw
