# Deploy the console to Fly.io and log in as admin — VENDOR / INTERNAL

Goal: get the console onto a public HTTPS URL and sign in as admin in a browser.
Run these from your Mac (you have the Fly account + push access; the cloud session
does not). The app config is in `fly.toml` at the repo root.

## 0. One-time prerequisites
```bash
brew install flyctl          # or: curl -L https://fly.io/install.sh | sh
fly auth signup              # or `fly auth login` if you already have an account
```

## 1. Create the app + persistent volume
Pick a globally-unique app name and set it in `fly.toml` (`app = "..."`).
```bash
fly apps create modelpilot-console            # use your chosen name
fly volumes create consoledata --region iad --size 1   # 1 GB is plenty for SQLite
```
(The volume name `consoledata` must match `[[mounts]] source` in `fly.toml`.)

## 2. Set secrets (NOT in fly.toml)
```bash
# Required — signs session cookies. Set ONCE and keep it stable (rotating logs
# everyone out; leaking it lets sessions be forged).
fly secrets set CONSOLE_SECRET=$(openssl rand -hex 32)

# Your admin login (temporary — used once to seed, password unset afterward).
fly secrets set ADMIN_EMAIL=you@yourco.com ADMIN_PASSWORD='a-strong-passphrase'

# Email (SMTP) — REQUIRED for transactional email: 2FA codes, password resets,
# pilot-request notifications, and budget/anomaly/sync alerts. Without it those
# flows still "work" but the message is only logged server-side (dev mode), never
# delivered — so set this before relying on 2FA or pilot-request alerts in
# production. Use any SMTP provider (e.g. Postmark, SES, SendGrid, Resend).
fly secrets set \
  SMTP_HOST=smtp.your-provider.com SMTP_PORT=587 \
  SMTP_USER=your-smtp-username SMTP_PASSWORD='your-smtp-password' \
  SMTP_FROM='Outlay <no-reply@outlay-ai.com>'
# Optional — where pilot-request ("Become a customer") form submissions are emailed
# (defaults to ADMIN_EMAIL). Also visible in the admin Leads inbox regardless.
# fly secrets set PILOT_INBOX=you@outlay-ai.com

# Optional — DEMO MODE allowlist. Comma-separated account emails allowed to toggle
# the in-app "demo mode" (one click seeds a fully worked customer — sample report,
# budgets, programs, a synced source — for live demos across both personas, then
# wipes back to a clean account on exit). UNSET = demo mode is hidden for everyone
# (the safe default). Only listed accounts ever see "Enter demo mode" or the
# "See it with sample data" controls; no prospect or customer can reach them.
# Not sensitive — can also live in fly.toml [env] instead of secrets.
# fly secrets set DEMO_ACCOUNT_EMAILS=you@outlay-ai.com
#   (multiple: DEMO_ACCOUNT_EMAILS='you@outlay-ai.com,demo@outlay-ai.com')

# Optional — SMS 2FA via Twilio (the 'sms' channel; email 2FA needs none of this):
# fly secrets set TWILIO_ACCOUNT_SID=AC... TWILIO_AUTH_TOKEN=... TWILIO_FROM='+15551234567'

# Optional — billing (the console runs fine without these):
# fly secrets set STRIPE_SECRET_KEY=sk_live_... STRIPE_PRICE_ID=price_... STRIPE_WEBHOOK_SECRET=whsec_...
# Optional — subscription tiers (flat monthly Stripe prices; set when pricing is decided):
# fly secrets set STRIPE_SELFOPT_PRICE_ID=price_...   # Self-optimize monthly subscription
# fly secrets set STRIPE_MANAGED_PRICE_ID=price_...   # Managed monthly subscription
#   (STRIPE_PRICE_ID = the metered price @ **$0.01/unit**, added to every checkout;
#    we report the bill in cents with the tier rate applied in code, so one price
#    bills 20% PAYG and 15% on subscription tiers correctly.)
```

> **Verify email works** after deploy: trigger a password reset (or enable 2FA in
> Settings) and confirm the message arrives. If it doesn't, check `fly logs` — a
> `[notify:dev]` line means SMTP isn't configured (the message was only logged).

## 3. Deploy
```bash
fly deploy                   # builds console/Dockerfile from the repo root
fly status                   # 1 machine, running, on the consoledata volume
```
You now have `https://<app>.fly.dev`. Visiting it serves the landing page.

## 4. Create your admin account, then lock it down
```bash
fly ssh console -C "python -m console.create_admin"   # idempotent; refuses weak pw
fly secrets unset ADMIN_PASSWORD                       # don't leave the pw in env
```

## 5. Log in
Open `https://<app>.fly.dev/login`, sign in with your ADMIN_EMAIL / ADMIN_PASSWORD.
Because the account's role is `admin`, you're routed straight to **/admin** (the
cross-customer overview + tuning-review queue). Done.

## 6. Custom domain — serve the product at app.outlay-ai.com
```bash
fly certs add app.outlay-ai.com           # prints the DNS records to add
```
Then in Cloudflare (the `outlay-ai.com` zone) add the records Fly shows, set to
**DNS only (grey cloud, not proxied)** so Fly can validate + serve TLS. Check with
`fly certs show app.outlay-ai.com` until it reads **Ready**. `CONSOLE_BASE_URL` in
`fly.toml` is already `https://app.outlay-ai.com`, so reset/login links use it after
the next `fly deploy`. The `<app>.fly.dev` route still works as a fallback but isn't
shared. (To drop the `modelpilot` Fly app name from that fallback entirely, recreate
the app under a new name — see "Renaming the app" below.)

## Notes
- **Never run more than one machine.** SQLite is single-writer. The app is set to
  **scale to zero** (`auto_stop_machines = "stop"`, `min_machines_running = 0`) to
  save cost — Fly stops it when idle and starts the same machine (with its volume)
  on the next request, with a brief cold start. Set `min_machines_running = 1` for
  always-on / no cold start.
- **Backups:** `fly volumes` snapshots the disk; take a snapshot before migrations.
  To pull a copy of the DB: `fly ssh sftp get /data/console.db ./console-backup.db`.
- **Customers** don't need any of this — they self-serve at `/signup` (14-day trial).
  This runbook is only for standing up the service + your admin login.
- This is the **console** only. `brain/` and `ingest/` deploy the same way (their
  own Dockerfiles); wire the brain to the console with `CONSOLE_URL=https://<app>`.
