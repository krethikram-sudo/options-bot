# Deploying ModelPilot (one command) — VENDOR / INTERNAL

Brings up the three backend services — **console**, **brain**, **ingest** — wired
together with persistent volumes. Customers point their gateway at the console;
the brain and ingest stay internal.

## Local / single-host

```bash
cp deploy/.env.example .env          # then set CONSOLE_SECRET (openssl rand -hex 32)
docker compose up -d --build
# create your admin login:
docker compose exec console \
  env ADMIN_EMAIL=you@co.com ADMIN_PASSWORD='a-strong-password' python -m console.seed
open http://localhost:8700           # sign in as the admin
```

That's the whole stack. The console serves the web app + machine API on **:8700**;
brain (:8600) and ingest (:8500) are reachable only inside the compose network.

## What's wired for you

| Service | Role | Talks to |
|---|---|---|
| **console** | accounts, dashboards, billing, machine API | — (the public entrypoint) |
| **brain** | routing decision + entitlement/mode | `CONSOLE_URL=http://console:8700` |
| **ingest** | opt-in aggregate telemetry | — |

The console knows the brain (`MODELPILOT_BRAIN_URL`) and ingest
(`MODELPILOT_INGEST_URL`, used by `/status`); the brain reads entitlement + approved
policy back from the console. No manual URL juggling.

## Production checklist

1. Put the **console behind HTTPS** (your platform's load balancer or a reverse
   proxy in front of `:8700`) and set `CONSOLE_BASE_URL=https://app.yourdomain` +
   `CONSOLE_SECURE_COOKIES=1` in `.env`.
2. Point a domain (e.g. `app.modelpilot.app`) at the console; that URL is what the
   landing-page CTAs and docs use.
3. (Optional) Set Stripe keys to turn on live billing, and SMTP for real emails.
4. Back up the three volumes (`braindata`, `ingestdata`, `consoledata`) — they hold
   accounts, billing, and metering (no prompt data).
5. Customers connect with:
   ```bash
   pip install modelpilot-client
   export MODELPILOT_BRAIN_URL=https://brain.yourdomain   # or expose brain via the proxy
   export MODELPILOT_CONSOLE_URL=https://app.yourdomain
   export MODELPILOT_API_KEY=mp_live_…                    # from the console Connect page
   modelpilot-client
   ```

To expose the brain to external gateways, add a `ports: ["8600:8600"]` to the brain
service (or route it through your proxy); for same-host gateways the internal
address is fine.

Hosted PaaS (Fly.io / Render / Railway) work too — deploy each Dockerfile as its own
app with a `/data` volume and the same env. See `brain/DEPLOY.md` and
`console/DEPLOY.md` for per-service notes.
