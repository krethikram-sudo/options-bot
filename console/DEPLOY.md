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

## 4. Billing (Stripe, usage-based: 20% PAYG / 15% on subscription tiers)

Create a **metered** recurring Price set to **$0.01 per unit (1 cent)**, linked to a
Meter. We compute the bill in code (`tier rate × realized savings`) and report it
**in cents**, so the $0.01/unit price bills the right percentage for every tier —
one Price covers PAYG (20%) and the 15% subscription tiers. Then set:
```bash
export STRIPE_SECRET_KEY=sk_live_...
export STRIPE_PRICE_ID=price_...            # the metered $0.01/unit price above
export STRIPE_SELFOPT_PRICE_ID=price_...    # flat $99/mo Self-optimize price
# export STRIPE_MANAGED_PRICE_ID=price_...  # flat Managed price (when set)
export STRIPE_WEBHOOK_SECRET=whsec_...       # optional, for /api/stripe/webhook
```
Convert-to-paid runs Stripe Checkout (subscription mode) to collect a card; as
savings are metered, `/api/meter` pushes the bill (cents) to the meter **and marks
the row reported** so the `sync_unreported_usage` backstop never double-bills.
`sync_unreported_usage` only bills paid accounts' **post-conversion** savings.
**Without** Stripe keys the console still runs end-to-end: convert records the plan
and metering accrues, to be reconciled once Stripe is connected.

## Security / privacy

- Passwords are PBKDF2-SHA256 (200k iterations); sessions are HMAC-signed cookies
  (`CONSOLE_SECRET`). Set `CONSOLE_SECURE_COOKIES=1` behind HTTPS.
- `/api/meter` accepts aggregate dollars + counts only and **rejects** any payload
  containing prompt/output/secret keys (422) — defense in depth.
- Change the seeded admin password immediately.
