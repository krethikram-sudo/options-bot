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

# Optional — billing (the console runs fine without these):
# fly secrets set STRIPE_SECRET_KEY=sk_live_... STRIPE_PRICE_ID=price_... STRIPE_WEBHOOK_SECRET=whsec_...
```

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

## 6. Custom domain (optional, do when ready)
```bash
fly certs add app.modelpilot.app          # then add the shown DNS records at your registrar
```
After the cert is issued, update `CONSOLE_BASE_URL` in `fly.toml` to
`https://app.modelpilot.app` and `fly deploy` again so reset/login links use it.

## Notes
- **Never scale past one machine.** SQLite is single-writer; this app expects one
  always-on instance (`min_machines_running = 1`, `auto_stop_machines = false`).
- **Backups:** `fly volumes` snapshots the disk; take a snapshot before migrations.
  To pull a copy of the DB: `fly ssh sftp get /data/console.db ./console-backup.db`.
- **Customers** don't need any of this — they self-serve at `/signup` (7-day trial).
  This runbook is only for standing up the service + your admin login.
- This is the **console** only. `brain/` and `ingest/` deploy the same way (their
  own Dockerfiles); wire the brain to the console with `CONSOLE_URL=https://<app>`.
