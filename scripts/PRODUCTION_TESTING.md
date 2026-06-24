# Production testing — real-data validation

Two one-command checks for the deployed Outlay console. Both are stdlib-only
(`urllib`), so they run anywhere with no install.

## 1. Pre-flight: "is prod healthy?"

```
python scripts/preflight.py                          # checks app.outlay-ai.com
python scripts/preflight.py --base http://127.0.0.1:8700
python scripts/preflight.py --strict                 # fail on warnings too (CI gate)
```

Reads only the public `/api/health` endpoint (no creds, no secrets) and grades:

- **App liveness** + billing mode.
- **Scheduler freshness** — the digest / close-pack / retention / webhook-redelivery
  sweeps only run if the scheduler is hitting the cron endpoints. Stale = silent failure.
- **Report-blob storage ceiling** — the JSON-in-SQLite scale watch.
- **Deployment readiness** (non-secret booleans): SMTP configured (else 2FA codes /
  resets / alerts are logged-only, not sent), connector-token encryption key set,
  secure cookies, `CONSOLE_BASE_URL` set.

Exit codes: `0` healthy (or warnings), `1` warnings under `--strict`, `2` critical
(unreachable, or encryption key missing). Drops into a deploy gate / cron monitor.

A fully-configured prod box looks like this (diff your real output against it):

```
App
  ✓ liveness                   /api/health responded ok
Scheduler (background sweeps)
  ✓ sync-due                   last run 12m ago
  ✓ digest-due                 last run 12m ago
Report storage
  ✓ blob size                  largest report 1.2 MB
Deployment readiness
  ✓ SMTP configured            transactional email will send
  ✓ encryption key set         connector tokens encrypted at rest
  ✓ secure cookies             Secure flag on session cookie
  ✓ base URL set               CONSOLE_BASE_URL configured
Result: READY — all checks passed ✓
```

Right after a deploy the scheduler jobs read "stale / never" until the first
in-process sweep runs (~hourly) — that's a warning, not a failure.

## Automated monitor (GitHub Actions)

`.github/workflows/prod-health.yml` runs the pre-flight against prod **hourly**
(and on demand via the Actions tab → "Run workflow" — use that right after a
`make deploy`). It fails the run only on a *critical* (prod unreachable or the
encryption key missing), so you get an Actions-failure email when prod is
genuinely down, without noise from a transiently-stale scheduler.

- Override the target with a repo **variable** `PROD_BASE_URL` (default
  `https://app.outlay-ai.com`).
- Add repo **secrets** `OUTLAY_SMOKE_EMAIL` / `OUTLAY_SMOKE_PASSWORD` (a dedicated
  MFA-free smoke account) to also run the `--no-sync` login + page-render smoke
  on every check. Without them, that step is skipped.

## 2. End-to-end smoke: real data through the real console

```
OUTLAY_SMOKE_EMAIL=smoke@you.com OUTLAY_SMOKE_PASSWORD=… \
OUTLAY_GITHUB_OWNER=acme OUTLAY_GITHUB_REPO=app OUTLAY_GITHUB_TOKEN=ghp_… \
OUTLAY_ANTHROPIC_KEY=sk-ant-admin-… \
python scripts/smoke_outlay_e2e.py
```

Signs in, **connects real read-only sources, runs a live sync, and verifies the
report renders** — exercising the live connectors, at-rest token encryption, the
sync pipeline, every customer page, and finally scraping the two numbers that
decide the bet: **AI spend** and **ticket coverage**.

Modes:
- **real-data** (default when connection creds are supplied) — connect + sync + verify.
- `--sample` — bundled sample data (needs a demo-flagged account: `DEMO_ACCOUNT_EMAILS`).
- `--no-sync` — just sign in and verify pages render (smoke the deploy without tokens).

Flags: `--tracker {github,jira,linear}`, `--persona {eng,business}`, `--signup`
(creates the account first — use a throwaway, it writes to the target DB).

Connection creds via env: `OUTLAY_GITHUB_OWNER/REPO/TOKEN`, `OUTLAY_ANTHROPIC_KEY`,
`OUTLAY_CURSOR_KEY`, `OUTLAY_JIRA_BASE_URL/EMAIL/TOKEN/JQL`, `OUTLAY_LINEAR_KEY`.

**Use a dedicated smoke account (no MFA) and read-only tokens — never a real
customer's.**

## Recommended order to de-risk a launch

1. `preflight.py` against the deployed URL — confirm the box is configured right.
2. `smoke_outlay_e2e.py --no-sync` — confirm signup/login/pages work post-deploy.
3. `smoke_outlay_e2e.py` with **your own** read-only GitHub+Anthropic creds —
   confirm a live sync attributes real spend (watch the coverage number).
4. The ground-truth check: in-product, paste a provider **cost export** and confirm
   Outlay reconciles to the **actual invoice** within N%.
5. A 2-week design-partner pilot on a real team — the only test that yields a
   measured coverage + forecast-accuracy (MdAPE) number on real data.
   (See `outlay/VALIDATION.md` for what public data already de-risked.)
