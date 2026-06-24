#!/usr/bin/env python3
"""Outlay production pre-flight — one command to answer "is prod healthy?".

Hits the deployed console's health endpoint and grades it: app liveness,
scheduler freshness (so the digest / close-pack / retention / redelivery sweeps
are actually running), the report-blob storage ceiling, and the deployment
readiness flags (SMTP configured, connector-token encryption key set, secure
cookies, base URL). Exits non-zero if anything CRITICAL is wrong, so it drops
straight into CI / a deploy gate / a cron monitor.

    python scripts/preflight.py                         # checks app.outlay-ai.com
    python scripts/preflight.py --base http://127.0.0.1:8700
    OUTLAY_BASE_URL=https://staging.example python scripts/preflight.py

Stdlib only (urllib) so it runs anywhere with no install. Reads only the public
/api/health endpoint — no credentials, no secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _c(color: str, s: str) -> str:
    return f"{color}{s}{RST}" if sys.stdout.isatty() else s


def _fmt_bytes(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _fmt_age(seconds) -> str:
    if seconds is None:
        return "never"
    s = int(seconds)
    if s < 90:
        return f"{s}s ago"
    if s < 5400:
        return f"{s // 60}m ago"
    if s < 172800:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def fetch_health(base: str, timeout: float = 10.0) -> dict:
    url = base.rstrip("/") + "/api/health"
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (trusted base)
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Outlay production pre-flight health check.")
    ap.add_argument("--base", default=os.environ.get("OUTLAY_BASE_URL", "https://app.outlay-ai.com"),
                    help="console base URL (default: app.outlay-ai.com or $OUTLAY_BASE_URL)")
    ap.add_argument("--strict", action="store_true",
                    help="also FAIL on warnings (SMTP/secure-cookies/storage), not just criticals")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    print("=" * 70)
    print(f"Outlay pre-flight — {base}")
    print("=" * 70)

    try:
        h = fetch_health(base)
    except Exception as e:  # noqa: BLE001
        print(_c(RED, f"\n✗ CRITICAL  could not reach {base}/api/health — {e}"))
        print("\nResult: " + _c(RED, "NOT REACHABLE") + " (is the console deployed and up?)")
        return 2

    criticals: list[str] = []
    warnings: list[str] = []

    def line(label: str, ok: bool, detail: str = "", *, warn: bool = False) -> None:
        if ok:
            mark = _c(GREEN, "✓")
        elif warn:
            mark = _c(YEL, "!")
        else:
            mark = _c(RED, "✗")
        print(f"  {mark} {label:<26} {_c(DIM, detail)}")

    # --- App liveness -------------------------------------------------------
    print("\nApp")
    alive = bool(h.get("ok"))
    line("liveness", alive, "/api/health responded ok" if alive else "ok != true")
    if not alive:
        criticals.append("app not live")
    line("billing (stripe)", True,
         "enabled" if h.get("stripe") else "disabled (fine for pilots)", warn=False)

    # --- Scheduler ----------------------------------------------------------
    print("\nScheduler (background sweeps)")
    cron = h.get("cron") or {}
    if not cron:
        line("jobs", False, "no cron data reported", warn=True)
        warnings.append("scheduler health unavailable")
    for job, c in cron.items():
        fresh = not c.get("stale", True)
        line(job, fresh, f"last run {_fmt_age(c.get('age_seconds'))}",
             warn=not fresh)
        if not fresh:
            warnings.append(f"cron '{job}' stale")
    if not h.get("cron_ok", True):
        warnings.append("a scheduled job is overdue")

    # --- Storage ceiling ----------------------------------------------------
    print("\nReport storage")
    storage_ok = h.get("storage_ok", True)
    line("blob size", storage_ok,
         f"largest report {_fmt_bytes(h.get('report_max_bytes'))}", warn=not storage_ok)
    if not storage_ok:
        warnings.append("a report blob is over the soft limit (plan aggregate storage)")

    # --- Deployment readiness ----------------------------------------------
    print("\nDeployment readiness")
    rd = h.get("readiness") or {}
    if not rd:
        line("readiness flags", False,
             "not reported (older build — deploy this branch)", warn=True)
        warnings.append("readiness flags unavailable")
    else:
        # SMTP: critical for prod (2FA codes, resets, digests, alerts all need it).
        smtp = rd.get("smtp_configured", False)
        line("SMTP configured", smtp,
             "transactional email will send" if smtp
             else "NO email will send (2FA / resets / alerts logged only)", warn=not smtp)
        if not smtp:
            warnings.append("SMTP not configured (email won't send)")
        # Connector-token encryption key: critical — tokens are stored at rest.
        sb = rd.get("secretbox_key_set", False)
        line("encryption key set", sb,
             "connector tokens encrypted at rest" if sb
             else "CONSOLE_SECRET / CONSOLE_SECRETBOX_KEY MISSING", warn=False)
        if not sb:
            criticals.append("encryption key not set (connector tokens at risk)")
        # Secure cookies: important once on HTTPS.
        sc = rd.get("secure_cookies", False)
        line("secure cookies", sc,
             "Secure flag on session cookie" if sc
             else "set CONSOLE_SECURE_COOKIES=1 in prod", warn=not sc)
        if not sc:
            warnings.append("secure cookies off (set CONSOLE_SECURE_COOKIES=1)")
        bu = rd.get("base_url_set", False)
        line("base URL set", bu,
             "CONSOLE_BASE_URL configured" if bu else "CONSOLE_BASE_URL unset", warn=not bu)
        if not bu:
            warnings.append("CONSOLE_BASE_URL unset (links / passkeys may break)")

    # --- Verdict ------------------------------------------------------------
    print("\n" + "=" * 70)
    if criticals:
        print(_c(RED, f"Result: NOT READY — {len(criticals)} critical, {len(warnings)} warning(s)"))
        for c in criticals:
            print(_c(RED, f"  ✗ {c}"))
        for w in warnings:
            print(_c(YEL, f"  ! {w}"))
        return 2
    if warnings and args.strict:
        print(_c(RED, f"Result: NOT READY (strict) — {len(warnings)} warning(s)"))
        for w in warnings:
            print(_c(YEL, f"  ! {w}"))
        return 1
    if warnings:
        print(_c(YEL, f"Result: LIVE with {len(warnings)} warning(s)"))
        for w in warnings:
            print(_c(YEL, f"  ! {w}"))
        return 0
    print(_c(GREEN, "Result: READY — all checks passed ✓"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
