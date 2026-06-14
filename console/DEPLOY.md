# Deploying the ModelPilot console — VENDOR / INTERNAL

The console is the third vendor service (with `brain/` and `ingest/`). It owns
accounts, the web UI, and billing. Customers reach it in a browser; the brain and
gateways reach it over the machine API.

| Service | Purpose | Port | Persists at /data | Public? |
|---|---|---|---|---|
| **console** | web app + accounts + billing + machine API | 8700 | `console.db` | yes (customers log in) |
| **brain** | routing decision + entitlement (reads console) | 8600 | `brain.db` | no (gateways only) |
| **ingest** | opt-in aggregate telemetry | 8500 | `ingest.db` | no |

## 1. Build & run

```bash
docker build -f console/Dockerfile -t modelpilot-console .
docker run -p 8700:8700 -v $PWD/consoledata:/data \
  -e CONSOLE_SECRET=$(openssl rand -hex 32) \
  -e CONSOLE_BASE_URL=https://app.modelpilot.app \
  -e MODELPILOT_BRAIN_URL=https://brain.modelpilot.app \
  modelpilot-console
# create your admin login:
docker exec <ctr> env ADMIN_EMAIL=you@co.com ADMIN_PASSWORD=secret python -m console.seed
```

Fly.io / Render / a VM all work the same way: build the Dockerfile, mount a volume
at `/data`, expose 8700, put it behind HTTPS, and set `CONSOLE_SECURE_COOKIES=1`.
Point a domain (e.g. `app.modelpilot.app`) at it — that's the URL in the landing
page CTAs.

## 2. Wire the brain to the console

Set on the **brain**:
```bash
export CONSOLE_URL=https://app.modelpilot.app
```
Now the brain reads entitlement + routing mode from the console: a deployment is
entitled while its account is on an active trial or paid plan, and decisions are
auto-applied only when the account's mode is **autopilot** (guidance/shadow →
recommend only). No `CONSOLE_URL` → the brain falls back to its own license/trial.

## 3. Customer connection (shown on the Connect page)

```bash
pip install modelpilot-client
export MODELPILOT_BRAIN_URL=https://brain.modelpilot.app
export MODELPILOT_CONSOLE_URL=https://app.modelpilot.app
export MODELPILOT_DEPLOYMENT_ID=dep_...        # issued at signup
modelpilot-client
```
The gateway reports realized savings to the console every minute (aggregate `$` +
counts only; `modelpilot meter --watch` is the standalone equivalent for cron).

## 4. Billing (Stripe, usage-based: 20% of realized savings)

Create a **metered** recurring Price where 1 unit = $1 of savings and the unit
amount is your rate (default $0.20). Then set:
```bash
export STRIPE_SECRET_KEY=sk_live_...
export STRIPE_PRICE_ID=price_...           # the metered price above
export STRIPE_WEBHOOK_SECRET=whsec_...      # optional, for /api/stripe/webhook
```
Convert-to-paid runs Stripe Checkout (subscription mode) to collect a card; as
savings are metered we push usage records (= dollars of savings) onto the
subscription item, so Stripe invoices `rate × savings` each cycle. Schedule
`console.stripe_billing.sync_unreported_usage` (or rely on per-report pushes) to
reconcile. **Without** Stripe keys the console still runs end-to-end: convert
records the plan and metering accrues, to be reconciled once Stripe is connected.

## Security / privacy

- Passwords are PBKDF2-SHA256 (200k iterations); sessions are HMAC-signed cookies
  (`CONSOLE_SECRET`). Set `CONSOLE_SECURE_COOKIES=1` behind HTTPS.
- `/api/meter` accepts aggregate dollars + counts only and **rejects** any payload
  containing prompt/output/secret keys (422) — defense in depth.
- Change the seeded admin password immediately.
