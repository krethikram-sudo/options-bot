# Routing brain (split architecture, v1) — VENDOR-SIDE / INTERNAL

This runs on **our** infrastructure. It is not shipped to customers and not in
the migrate/publish paths. It exists so the local client can eventually be
**published safely**: the defensible IP and the monetization gate live here.

## What the brain holds (and the client does not)
- The routing **policy**: per-category floors, the structured-output/tool guard,
  switch **economics** (cache-aware net-benefit), and the calibrated confidence
  gate — all improvable server-side without shipping client updates.
- **Server-authoritative entitlement**: a valid license, else a 7-day trial keyed
  by deployment id (first-seen recorded here). Editing the client cannot grant
  entitlement — no decision is returned without it.
- (Next) per-customer learned policy (floors/gates/rules) keyed by deployment.

## What the client sends (and never sends)
`POST /route` receives a category label, a confidence, the requested model, and
**numeric/boolean features only** (token estimates, flags). It **never** receives
prompt text, model outputs, or API keys — and `/route` returns 422 if a payload
contains any of those keys (defense in depth). Keys and prompts stay on the
client, which forwards to Anthropic directly with the customer's own key.

## Endpoints
- `POST /route` → `{entitled, action, recommended_model, apply, gate, rationale, entitlement}`
- `GET /health`

## Run
```bash
pip install fastapi uvicorn
BRAIN_DB=brain.db PORT=8600 python -m brain.server
```
Client side: `modelpilot/brain_client.py` (`remote_decide`) — fail-open if the
brain is unreachable. Tests: `python -m pytest brain/ -q`.

## Status (v1) & next steps
Built: the brain decision service, server-side license/trial enforcement, the
no-sensitive-data guarantee, and the client seam (`brain_client.remote_decide`).
Not yet done (deliberate, next): wire the live gateway to call the brain when
`MODELPILOT_BRAIN_URL` is set (fail-open to local), then carve a **thin client
package** that ships the proxy + `brain_client` *without* the router/taxonomy/
economics — that's the artifact that's safe to publish to PyPI.
