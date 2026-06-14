# ModelPilot console — VENDOR / INTERNAL

The customer-facing SaaS control plane. Runs on **our** infrastructure (alongside
`brain/` and `ingest/`). **Not** part of the shipped `modelpilot` package and
**not** migrated/published to the customer repo.

## What it is

A single FastAPI service (server-rendered, no build step) that delivers the whole
product through the browser:

**Customers** — land → sign up → 7-day free trial → convert to a paid plan
(billed **20% of the savings we deliver**). Once signed in they get a dashboard
(realized savings, baseline vs actual, current bill), a **mode toggle**
(shadow / guidance / autopilot), routing-policy settings (risk, quality floor,
telemetry opt-in), connection instructions, and billing.

**Admin (you)** — a cross-customer overview (revenue + savings this cycle and
lifetime), per-customer drill-down (per-category routed/escalation/savings +
auto-suggested tuning actions to improve the product), and access management
(extend trial, mark paid, suspend/reactivate, set rate).

## How it fits the rest of the system

```
 browser ─┬─ customer app (dashboard, mode toggle, billing)
          └─ admin console (revenue, manage access, per-customer data)
                         │
 console  ── /api/entitlement ──►  brain   (reads entitlement + mode; mode=autopilot ⇒ apply)
          ◄─ /api/meter ─────────  gateway (reports realized savings; dollars + counts only)
                         │
                       Stripe (usage-based: 20% of realized savings)
```

- **Mode is server-authoritative.** The toggle writes `settings.mode`; the brain
  reads it via `/api/entitlement` and only auto-routes (`apply`) in autopilot.
- **Billing is on realized savings.** Gateways post the savings delta to
  `/api/meter` (aggregate `$` + counts — sensitive keys are rejected, 422). The
  bill each cycle is `rate × realized_savings`; usage is pushed to Stripe.

## Run

```bash
pip install -r console/requirements.txt
CONSOLE_DB=console.db CONSOLE_SECRET=$(openssl rand -hex 32) python -m console.server
# http://127.0.0.1:8700  ·  seed demo data + an admin login:
ADMIN_EMAIL=you@co.com ADMIN_PASSWORD=secret CONSOLE_DB=console.db python -m console.seed
```

Env: `CONSOLE_DB`, `CONSOLE_SECRET`, `CONSOLE_BASE_URL`, `MODELPILOT_BRAIN_URL`,
`CONSOLE_SECURE_COOKIES=1` (behind HTTPS), and Stripe (`STRIPE_SECRET_KEY`,
`STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`). See `DEPLOY.md`.
