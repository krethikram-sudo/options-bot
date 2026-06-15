# ModelPilot — repo guide for Claude

**Read `TODO.md` first** — it's the founder's running to-do list and the source of truth
for current state, live URLs, and what's next. Keep it updated as work completes.

## What this is
ModelPilot: a drop-in cost-routing gateway for the Claude API that routes each request to
the cheapest model that's provably good enough, billed at 20% of realized savings.

## Architecture (split, IP-protecting)
- `modelpilot/` — the shipped, publishable thin client + commodity classifier (`router_classify.py`).
  Customer's API key and prompts **never leave their box**. This is the only part migrated/published
  to the customer repo.
- `brain/` — vendor-internal routing decision + entitlement (reads the console). **Not** shipped.
- `console/` — vendor-internal SaaS control plane (accounts, admin, billing, machine API). **Not** shipped.
- `ingest/` — vendor-internal opt-in aggregate telemetry. **Not** shipped.

## Deploys (Fly.io, free `.fly.dev` route)
- Console: root `fly.toml` → `modelpilot-console-prod`. Runbook: `console/FLY_DEPLOY.md`.
- Brain: `brain/fly.toml` → `modelpilot-brain-prod` (deploy with `-c brain/fly.toml --dockerfile brain/Dockerfile`). Runbook: `brain/FLY_DEPLOY.md`.

## Working rules (from the founder)
- Push only to `krethikram-sudo/options-bot` — branches `main` and `claude/cool-mendel-slhcz7`.
- `brain/`, `console/`, `ingest/` are vendor-internal — never migrate/publish them to the customer repo.
- Keep savings claims honest/substantiated; prompts/outputs/keys never leave the customer box.
- Never paste secrets (API keys, the license private key) into chat or commits.
