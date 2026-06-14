"""Beta license gate — revocable, named, expiring tokens that gate AUTOPILOT.

Scope, stated honestly: this is a *deterrent and usage control* for the private
beta. It ensures autopilot only runs with a token we issued, that tokens carry a
named licensee (accountability) and an expiry (revocation by lapse), and it lets
us turn a copy off by not renewing. It is NOT unbreakable DRM — the HMAC secret
ships in the client, so a determined reverse-engineer could forge a token. Real
IP protection comes from (1) the LICENSE terms and (2) moving the routing brain
server-side; see internal/SPLIT_ARCHITECTURE.md. The interface here is built so
the verification backend can later swap to asymmetric keys or a server check
without touching callers.

Guidance/shadow run WITHOUT a license (the funnel — prospects must be able to see
their potential savings freely). Autopilot — capturing savings — requires a token.

Token:  base64url(json_claims) "." base64url(hmac_sha256(claims, SECRET))
Claims: {"licensee": str, "exp": unix_ts|null, "features": [...], "iat": unix_ts}
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

# Beta cohort signing secret (deterrent only — see module docstring).
_SECRET = b"ac2a166716d82135ff232c24b7ab39946bfc70340d59d1f104b37173855e5af1"


class LicenseError(Exception):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _ub64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(claims: dict, secret: bytes = _SECRET) -> str:
    payload = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(secret, payload, hashlib.sha256).digest()
    return _b64(payload) + "." + _b64(sig)


def verify_token(token: str, secret: bytes = _SECRET) -> dict:
    try:
        p_b64, s_b64 = token.strip().split(".")
        payload, sig = _ub64(p_b64), _ub64(s_b64)
    except Exception as e:  # noqa: BLE001
        raise LicenseError("malformed license token") from e
    if not hmac.compare_digest(sig, hmac.new(secret, payload, hashlib.sha256).digest()):
        raise LicenseError("invalid license signature")
    claims = json.loads(payload)
    exp = claims.get("exp")
    if exp and time.time() > exp:
        raise LicenseError("license expired on " + time.strftime("%Y-%m-%d", time.gmtime(exp)))
    return claims


def check(value: str | None = None) -> dict | None:
    """Resolve a license from `value` or MODELPILOT_LICENSE (a token, or @/path
    to a file containing one). Returns claims if valid, None if no token is
    present, and raises LicenseError if a token is present but invalid/expired."""
    raw = value if value is not None else os.environ.get("MODELPILOT_LICENSE", "")
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("@"):
        with open(raw[1:]) as f:
            raw = f.read().strip()
    return verify_token(raw)


def main():
    """Issuer CLI (for us): mint a token. Needs the signing secret in the env or
    the embedded beta secret.  python -m modelpilot.license issue --licensee Acme --days 30"""
    import argparse

    p = argparse.ArgumentParser(description="ModelPilot license issuer")
    p.add_argument("action", choices=["issue", "verify"])
    p.add_argument("--licensee", default="")
    p.add_argument("--days", type=int, default=30, help="validity; 0 = never expires")
    p.add_argument("--token", default="", help="token to verify")
    args = p.parse_args()
    secret = os.environ.get("MODELPILOT_LICENSE_SECRET", "").encode() or _SECRET

    if args.action == "issue":
        now = int(time.time())
        claims = {"licensee": args.licensee, "iat": now,
                  "exp": (now + args.days * 86_400) if args.days else None,
                  "features": ["autopilot"]}
        print(make_token(claims, secret))
    else:
        try:
            print("valid:", verify_token(args.token, secret))
        except LicenseError as e:
            raise SystemExit(f"invalid: {e}")


if __name__ == "__main__":
    main()
