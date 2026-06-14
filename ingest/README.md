# Telemetry ingest (vendor-side, internal)

Receives the opt-in, aggregate-only telemetry that customers send via
`modelpilot telemetry` (see `modelpilot/telemetry.py`). **Runs on our
infrastructure** — it is NOT part of the shipped `modelpilot` package and is not
migrated/published to the customer repo.

## Run

```bash
pip install fastapi uvicorn httpx
INGEST_DB=ingest.db python -m ingest.server          # serves on 127.0.0.1:8500
```

Give a design partner the URL as their `MODELPILOT_TELEMETRY_URL`, e.g.
`https://t.yourhost.com/ingest`.

## Endpoints

- `POST /ingest` — store one aggregate payload. **Defense in depth:** it rejects
  (HTTP 422) any payload containing a forbidden key (`messages`, `prompt`,
  `content`, `output`, `api_key`, `example`, …) so we can never become the place
  sensitive data leaked to — even if a future client regressed.
- `GET /agg?since_days=30` — cross-deployment rollup for product tuning: mean
  catch-all rate, per-category volume + incident rate, and the top catch-all
  phrase signals summed across deployments. Uses the latest payload per
  deployment.
- `GET /actions?since_days=30` — turns the rollup into prioritized, concrete
  tuning actions: tighten a category (incident rate >2%), loosen a proven-safe
  high-volume category, run a recall pass (high catch-all rate), and add specific
  catch-all phrases to the matching starter pack / global recall. Also rendered
  at the top of the dashboard.
- `GET /dashboard?since_days=30` — the same rollup as a server-rendered HTML
  page (no JS/CDN): headline cards, a by-category volume/incident-rate table
  (incident rate >2% flagged red = tighten; high volume + low incident = loosen),
  and the top catch-all phrase signals. Open it in a browser to read the fleet at
  a glance.
- `GET /health`.

## How it drives the product

The rollup is the privacy-safe "regime-2" signal:
- **per-category incident rate across deployments** → where to tighten/loosen
  floors and gates;
- **mean catch-all rate + top catch-all phrases** → the next router-recall pass
  and starter-pack updates;
- all without any customer prompt text ever leaving their box.

## Tests

```bash
python -m pytest ingest/ -q
```
