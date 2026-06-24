#!/usr/bin/env python3
"""Outlay end-to-end production smoke — drive the REAL console over HTTP.

Signs in, connects real read-only sources, runs a sync, and verifies the report
renders — exercising the live connectors, at-rest token encryption, the sync
pipeline, and every customer page. This is the one check that proves the whole
product works against a running instance with real data, not just unit tests.

    # against the deployed console, with a dedicated smoke account:
    OUTLAY_SMOKE_EMAIL=smoke@you.com OUTLAY_SMOKE_PASSWORD=… \
    OUTLAY_GITHUB_OWNER=acme OUTLAY_GITHUB_REPO=app OUTLAY_GITHUB_TOKEN=ghp_… \
    OUTLAY_ANTHROPIC_KEY=sk-ant-admin-… \
    python scripts/smoke_outlay_e2e.py

    # local instance, just verify pages render against whatever data is there:
    python scripts/smoke_outlay_e2e.py --base http://127.0.0.1:8700 \
        --email a@b.com --password …  --no-sync

Modes:
  * real-data  (default when connection creds are supplied) — connect + sync + verify.
  * --sample   — populate via the bundled sample data (needs a demo-flagged account).
  * --no-sync  — skip the data step; just sign in and verify pages render.

Use a DEDICATED smoke-test account, not a real customer's. Read-only tokens only.
Stdlib only (urllib) so it runs anywhere with no install.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _c(color: str, s: str) -> str:
    return f"{color}{s}{RST}" if sys.stdout.isatty() else s


PASS, FAIL = _c(GREEN, "PASS ✓"), _c(RED, "FAIL ✗")


class Client:
    """Cookie-aware HTTP client over urllib (session cookie persists across calls)."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.HTTPRedirectHandler())

    def request(self, method: str, path: str, data: dict | None = None,
                timeout: float = 30.0):
        url = self.base + path
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method,
                                     headers={"accept": "application/json, text/html"})
        try:
            with self.opener.open(req, timeout=timeout) as r:  # noqa: S310 (trusted base)
                return r.status, r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, url, e.read().decode("utf-8", "replace")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, data, **kw):
        return self.request("POST", path, data=data, **kw)

    def has_session(self) -> bool:
        return any(ck.name == "mp_session" for ck in self.jar)


def env(*names: str) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def connection_fields(args) -> dict:
    """Build the /app/outlay/connect form payload from args/env, or {} if none given."""
    tracker = (args.tracker or "github").lower()
    f: dict[str, str] = {}
    anthropic = args.anthropic_key or env("OUTLAY_ANTHROPIC_KEY")
    cursor = args.cursor_key or env("OUTLAY_CURSOR_KEY")
    if tracker == "github":
        owner = args.github_owner or env("OUTLAY_GITHUB_OWNER")
        repo = args.github_repo or env("OUTLAY_GITHUB_REPO")
        token = args.github_token or env("OUTLAY_GITHUB_TOKEN", "GITHUB_TOKEN")
        if owner and repo:
            f.update(tracker="github", github_owner=owner, github_repo=repo,
                     github_token=token or "")
    elif tracker == "jira":
        base = env("OUTLAY_JIRA_BASE_URL")
        if base:
            f.update(tracker="jira", jira_base_url=base,
                     jira_email=env("OUTLAY_JIRA_EMAIL") or "",
                     jira_token=env("OUTLAY_JIRA_TOKEN") or "",
                     jira_jql=env("OUTLAY_JIRA_JQL") or "")
    elif tracker == "linear":
        key = env("OUTLAY_LINEAR_KEY")
        if key:
            f.update(tracker="linear", linear_key=key)
    if anthropic:
        f["anthropic_key"] = anthropic
    if cursor:
        f["cursor_key"] = cursor
    # Only a real data source (a tracker or an AI-usage key) counts as "connectable".
    has_source = any(k in f for k in ("github_owner", "jira_base_url", "linear_key")) \
        or "anthropic_key" in f or "cursor_key" in f
    return f if has_source else {}


def extract_number(html: str, kind: str, *needles: str) -> str:
    """Best-effort scrape of a labelled number near one of the needle phrases.
    `kind` is 'money' ($...) or 'pct' (n%) — kept specific so we don't grab a stray
    CSS width:100% as if it were a real figure (it's '?' when there's no report)."""
    import re
    pat = r"\$[\d,]+(?:\.\d+)?" if kind == "money" else r"\b\d{1,3}(?:\.\d+)?%"
    for needle in needles:
        i = html.find(needle)
        if i == -1:
            continue
        window = html[max(0, i - 160): i + 160]
        # skip percentages that are obviously layout (width:NN% / NN% in a style attr)
        for m in re.finditer(pat, window):
            ctx = window[max(0, m.start() - 12): m.start()]
            if kind == "pct" and ("width" in ctx or ":" in ctx[-2:]):
                continue
            return m.group(0)
    return "?"


def main() -> int:
    ap = argparse.ArgumentParser(description="Outlay end-to-end production smoke test.")
    ap.add_argument("--base", default=os.environ.get("OUTLAY_BASE_URL", "https://app.outlay-ai.com"))
    ap.add_argument("--email", default=os.environ.get("OUTLAY_SMOKE_EMAIL"))
    ap.add_argument("--password", default=os.environ.get("OUTLAY_SMOKE_PASSWORD"))
    ap.add_argument("--signup", action="store_true",
                    help="create the account first (pollutes the target DB — use a throwaway)")
    ap.add_argument("--company", default="Smoke Test Co")
    ap.add_argument("--persona", default="eng", choices=["eng", "business"],
                    help="first-run view to select past the persona gate (default: eng)")
    ap.add_argument("--sample", action="store_true", help="use bundled sample data (demo account only)")
    ap.add_argument("--no-sync", action="store_true", help="skip the data step; just verify pages render")
    ap.add_argument("--tracker", default=None, choices=["github", "jira", "linear"])
    ap.add_argument("--github-owner", default=None)
    ap.add_argument("--github-repo", default=None)
    ap.add_argument("--github-token", default=None)
    ap.add_argument("--anthropic-key", default=None)
    ap.add_argument("--cursor-key", default=None)
    args = ap.parse_args()

    base = args.base.rstrip("/")
    print("=" * 72)
    print(f"Outlay end-to-end smoke — {base}")
    print("=" * 72)

    if not args.email or not args.password:
        print(_c(RED, "Need --email/--password (or OUTLAY_SMOKE_EMAIL/PASSWORD)."))
        return 2

    cl = Client(base)
    failures = 0

    def step(name: str, ok: bool, detail: str = "") -> bool:
        nonlocal failures
        print(f"  {PASS if ok else FAIL}  {name:<34} {_c(DIM, detail)}")
        if not ok:
            failures += 1
        return ok

    # 1. Health
    st, _, body = cl.get("/api/health")
    try:
        h = json.loads(body)
    except Exception:  # noqa: BLE001
        h = {}
    step("health endpoint", st == 200 and h.get("ok") is True, f"HTTP {st}")

    # 2. (optional) signup
    if args.signup:
        st, url, _ = cl.post("/signup", {"email": args.email, "password": args.password,
                                         "company": args.company, "name": "Smoke Test",
                                         "accept": "1"})
        step("signup", cl.has_session() or st in (303, 200), f"HTTP {st}")

    # 3. Login
    if not cl.has_session():
        st, url, _ = cl.post("/login", {"email": args.email, "password": args.password})
        # success → session cookie + redirected into /app (not back to /login/verify)
        ok = cl.has_session() and "/login" not in url
        step("login", ok, f"HTTP {st} → {url.replace(base, '') or '/'}")
        if not ok:
            print(_c(YEL, "    (2FA-enabled or wrong creds? use a smoke account without MFA)"))

    st, url, body = cl.get("/app")
    step("authenticated /app", st == 200 and "/login" not in url, f"HTTP {st}")
    if failures:
        print(_c(RED, "\nCannot proceed without an authenticated session."))
        return 2

    # A brand-new account lands on the first-run persona gate, which overlays the real
    # dashboard until a view is chosen. Pick one (idempotent) so the populated pages
    # render — exactly what a real first-run user does.
    cl.post("/app/persona", {"persona": args.persona})

    # 4. Data step
    conn = connection_fields(args)
    if args.no_sync:
        print(_c(DIM, "  · data step skipped (--no-sync)"))
    elif args.sample:
        st, _, _ = cl.post("/app/outlay/sample", {})
        step("load sample data", st in (200, 303), f"HTTP {st}")
    elif conn:
        st, _, _ = cl.post("/app/outlay/connect", conn)
        step("save connection", st in (200, 303),
             f"tracker={conn.get('tracker', 'github')} HTTP {st}")
        st, _, body = cl.post("/app/outlay/sync", {})
        try:
            res = json.loads(body)
        except Exception:  # noqa: BLE001
            res = {}
        ok = res.get("ok") is True
        step("sync (live pull + attribute)", ok,
             "ok" if ok else f"error: {res.get('error', body[:120])!r}")
    else:
        print(_c(YEL, "  ! no connection creds supplied — verifying pages on existing data only"))

    # 5. Every customer page renders
    print("\nPages render (HTTP 200):")
    pages = [
        ("/app", "Overview"),
        ("/app/outlay", "Spend"),
        ("/app/outlay/estimate", "Estimate"),
        ("/app/outlay/accuracy", "Accuracy"),
        ("/app/outlay/budgets", "Budgets"),
        ("/app/outlay/governance", "Governance"),
        ("/app/outlay/connect", "Connect"),
        ("/app/settings", "Settings"),
        ("/app/security", "Security"),
    ]
    spend_html = ""
    for path, label in pages:
        st, url, body = cl.get(path)
        ok = st == 200 and "/login" not in url
        step(label, ok, path)
        if path == "/app/outlay":
            spend_html = body

    # 6. The two validation numbers (best-effort scrape)
    if spend_html:
        total = extract_number(spend_html, "money", "spend · window", "AI spend", "Total")
        coverage = extract_number(spend_html, "pct", "Mapped to a ticket", "ticket coverage",
                                  "mapped to a ticket")
        print("\nValidation read (from the Spend page):")
        print(f"    AI spend (window):   {_c(GREEN, total)}")
        print(f"    Ticket coverage:     {_c(GREEN, coverage)}   "
              + _c(DIM, "← the make-or-break number on real data"))

    print("\n" + "=" * 72)
    if failures:
        print(_c(RED, f"Result: {failures} FAILED — investigate before trusting prod."))
        return 1
    print(_c(GREEN, "Result: end-to-end smoke PASSED ✓"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
