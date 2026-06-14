"""License gate for autopilot — named, expiring, revocable tokens.

Two signing backends, auto-selected:

  * **Ed25519 (asymmetric) — preferred.** If a public key is bundled at
    modelpilot/license_pubkey.pem, the client verifies tokens with it and CANNOT
    mint them; only the holder of the matching private key (you) can issue.
    Unforgeable offline. This is the real gate.
  * **HMAC (symmetric) — beta fallback.** Used only when no public key is
    bundled yet. The verifying secret ships in the client, so it's a deterrent
    and usage control, not unbreakable DRM. Once a public key is present, HMAC
    tokens are rejected (no silent downgrade).

Set it up once (on a machine with a working `cryptography` install — e.g. your
Mac or CI):

    python -m modelpilot.license keygen     # writes the private key (keep secret),
                                            # prints the public key to bundle
    # commit modelpilot/license_pubkey.pem ; keep the private key out of git
    python -m modelpilot.license issue --key license_private_key.pem \
        --licensee "Acme Corp" --days 30

Guidance/shadow run WITHOUT a license (the funnel); autopilot requires a token.
crypto is imported lazily so the package never hard-depends on it at import time.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

# Beta HMAC fallback secret (deterrent only — used until a public key is bundled).
_SECRET = b"ac2a166716d82135ff232c24b7ab39946bfc70340d59d1f104b37173855e5af1"
_PUBKEY_PATH = os.path.join(os.path.dirname(__file__), "license_pubkey.pem")


class LicenseError(Exception):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _ub64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _ed25519_active() -> bool:
    return os.path.exists(_PUBKEY_PATH)


# --- minting (issuer side) --------------------------------------------------

def make_token(claims: dict, secret: bytes = _SECRET) -> str:
    """HMAC token (fallback / tests)."""
    payload = json.dumps({**claims, "alg": "hmac"}, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(secret, payload, hashlib.sha256).digest()
    return _b64(payload) + "." + _b64(sig)


def make_token_ed25519(claims: dict, private_key_pem: bytes) -> str:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = load_pem_private_key(private_key_pem, password=None)
    payload = json.dumps({**claims, "alg": "ed25519"}, separators=(",", ":"), sort_keys=True).encode()
    sig = key.sign(payload)
    return _b64(payload) + "." + _b64(sig)


# --- verification (client side) ---------------------------------------------

def verify_token(token: str, secret: bytes = _SECRET) -> dict:
    try:
        p_b64, s_b64 = token.strip().split(".")
        payload, sig = _ub64(p_b64), _ub64(s_b64)
        claims = json.loads(payload)
    except Exception as e:  # noqa: BLE001
        raise LicenseError("malformed license token") from e
    alg = claims.get("alg", "hmac")

    if _ed25519_active():
        # Asymmetric mode: only Ed25519 tokens are accepted (no downgrade).
        if alg != "ed25519":
            raise LicenseError("legacy/HMAC token rejected — this build verifies Ed25519 only")
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        with open(_PUBKEY_PATH, "rb") as f:
            pub = load_pem_public_key(f.read())
        try:
            pub.verify(sig, payload)
        except InvalidSignature as e:
            raise LicenseError("invalid license signature") from e
    else:
        if alg != "hmac":
            raise LicenseError("Ed25519 token but no public key is bundled")
        if not hmac.compare_digest(sig, hmac.new(secret, payload, hashlib.sha256).digest()):
            raise LicenseError("invalid license signature")

    exp = claims.get("exp")
    if exp and time.time() > exp:
        raise LicenseError("license expired on " + time.strftime("%Y-%m-%d", time.gmtime(exp)))
    return claims


def check(value: str | None = None) -> dict | None:
    """Resolve a license from `value` or MODELPILOT_LICENSE (token, or @/path to a
    file). Returns claims if valid, None if absent, raises LicenseError if invalid."""
    raw = value if value is not None else os.environ.get("MODELPILOT_LICENSE", "")
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("@"):
        with open(raw[1:]) as f:
            raw = f.read().strip()
    return verify_token(raw)


# --- issuer CLI (for us) ----------------------------------------------------

def main():
    import argparse

    p = argparse.ArgumentParser(description="ModelPilot license issuer")
    p.add_argument("action", choices=["keygen", "issue", "verify"])
    p.add_argument("--licensee", default="")
    p.add_argument("--days", type=int, default=30, help="validity; 0 = never expires")
    p.add_argument("--key", default=os.environ.get("MODELPILOT_LICENSE_PRIVKEY", ""),
                   help="Ed25519 private key PEM path for issuing (omit = HMAC fallback)")
    p.add_argument("--token", default="")
    args = p.parse_args()

    if args.action == "keygen":
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        priv = Ed25519PrivateKey.generate()
        priv_pem = priv.private_bytes(serialization.Encoding.PEM,
                                      serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption())
        pub_pem = priv.public_key().public_bytes(serialization.Encoding.PEM,
                                                 serialization.PublicFormat.SubjectPublicKeyInfo)
        with open("license_private_key.pem", "wb") as f:
            f.write(priv_pem)
        os.chmod("license_private_key.pem", 0o600)
        print("Wrote license_private_key.pem  — KEEP SECRET, never commit it.")
        print("\nBundle this public key as modelpilot/license_pubkey.pem (safe to commit):\n")
        print(pub_pem.decode())
        return

    if args.action == "issue":
        now = int(time.time())
        claims = {"licensee": args.licensee, "iat": now,
                  "exp": (now + args.days * 86_400) if args.days else None,
                  "features": ["autopilot"]}
        if args.key:
            with open(args.key, "rb") as f:
                print(make_token_ed25519(claims, f.read()))
        else:
            print(make_token(claims))  # HMAC fallback
        return

    try:
        print("valid:", verify_token(args.token))
    except LicenseError as e:
        raise SystemExit(f"invalid: {e}")


if __name__ == "__main__":
    main()
