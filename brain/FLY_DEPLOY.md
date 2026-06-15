# Deploy the BRAIN to Fly.io — VENDOR / INTERNAL

The brain makes the routing decision and reads each account's entitlement + mode
from the console. The gateway customers run calls it via `MODELPILOT_BRAIN_URL`.
**No secrets needed** — it verifies licenses with the bundled public key and (with
`CONSOLE_URL` set, which `brain/fly.toml` already does) gets entitlement from the
console keylessly.

Run everything from your repo root on your Mac:
```
cd ~/options-bot
```

## 1. Get the latest config
```
git pull origin main
```
This brings down `brain/fly.toml`, the updated console `MODELPILOT_BRAIN_URL`, and
the docs that now show customers the real brain URL.

## 2. Create the brain app + its volume
```
fly apps create modelpilot-brain-prod
fly volumes create braindata --region iad --size 1 -a modelpilot-brain-prod
```
If `fly apps create` says the name is taken, pick another — and tell Claude so the
3 references (this app name, console `MODELPILOT_BRAIN_URL`, docs) get updated.

## 3. Deploy the brain
```
fly deploy -c brain/fly.toml --dockerfile brain/Dockerfile
```
The `--dockerfile` flag is **required**: it forces the Docker build context to the
repo root (your cwd) so the image includes the `modelpilot/` package the brain
imports. Without it, Fly resolves the Dockerfile relative to `brain/` and the
build fails (`brain/brain/Dockerfile` not found).

## 4. Re-deploy the console once
So the console's Connect page + /status show customers the real brain URL:
```
fly deploy
```
(That uses the root `fly.toml` — the console app.)

## 5. Verify
```
fly status -a modelpilot-brain-prod
curl https://modelpilot-brain-prod.fly.dev/health
```
`/health` should return ok. Then in your console `/status` page the "Routing brain"
component should read operational.

## Done — the full loop now works
A customer signs up → connects their gateway with the env vars shown on the Connect
page → the gateway asks the brain for each routing decision → the brain checks the
console for entitlement + mode (autopilot applies; guidance/shadow recommend only)
→ savings get metered back to the console.

## Notes
- **One machine only** (SQLite trial clock on the `braindata` volume). It's set to
  **scale to zero** to save cost; the gateway fails open during a cold start, so a
  request that arrives while the brain is waking just passes through unrouted. Set
  `min_machines_running = 1` for always-on / no cold start.
- **Fails open:** if the brain is unreachable, the gateway still sends traffic to
  Claude (unrouted). You degrade savings, never uptime.
- **ingest/** (opt-in aggregate telemetry) is optional — skip it unless you want
  fleet-wide stats; it deploys the same way with `ingest/Dockerfile` on port 8500.
- The license **private key never goes in this image** — only the bundled public
  key. Issue tokens on your own machine with `python -m modelpilot.license issue`.
