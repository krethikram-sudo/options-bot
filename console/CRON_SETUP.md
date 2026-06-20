# Background sweeps (cron) — setup & verification — VENDOR / INTERNAL

Outlay runs several **background sweeps**. If nothing drives them, the work
silently never happens (no digests, no monthly close packs, stale data isn't
re-synced, failed webhooks aren't redelivered, retention isn't enforced).

There are two sweeps:

| Sweep | What it does | Endpoint | `/admin/health` job |
|-------|--------------|----------|---------------------|
| **Auto-sync** | Re-syncs connected sources on each account's cadence; fires stale-data / repeated-failure alerts | `POST /internal/outlay/sync-due` | `sync-due` |
| **Maintenance** | Weekly spend digest, monthly finance close pack, durable webhook redelivery, data-retention purge | `POST /internal/outlay/digest-due` | `digest-due` |

Both sweeps are **idempotent and cadence-guarded** — only genuinely-due work
fires — so running them as often as hourly is safe.

---

## Recommended: in-process scheduler (single always-on machine)

The console runs as **one always-on Fly machine** (SQLite is single-writer), so
the simplest reliable setup is to let that machine drive the sweeps itself. No
external scheduler, nothing else to stand up.

This is already wired in `fly.toml`:

```toml
[env]
  OUTLAY_AUTOSYNC_EVERY_MIN = "60"      # auto-sync sweep, hourly
  OUTLAY_MAINTENANCE_EVERY_MIN = "60"   # maintenance sweep, hourly
```

Deploy and it just runs:

```bash
fly deploy
```

To disable a sweep, set its var to `"0"` (or remove it) and redeploy. The loops
start in the app's `startup` event and call the same code paths as the HTTP
endpoints, recording each run so `/admin/health` shows freshness.

> Why hourly and not daily? The per-account cadences (weekly digest, monthly
> close pack, retention window, webhook backoff) are enforced inside the sweep,
> so an hourly tick just means *faster recovery* for sync failures and webhook
> redelivery, with no duplicate digests/close-packs.

---

## Alternative: external scheduler

If you'd rather drive the sweeps from outside (e.g. you later run more than one
service, or want them centralized), set `OUTLAY_AUTOSYNC_EVERY_MIN=0` and
`OUTLAY_MAINTENANCE_EVERY_MIN=0`, set a shared secret, and POST the endpoints on
a schedule.

```bash
fly secrets set OUTLAY_CRON_TOKEN=$(openssl rand -hex 24)
```

Both endpoints require `Authorization: Bearer $OUTLAY_CRON_TOKEN`. Hit each at
least daily (hourly is fine):

```bash
curl -fsS -X POST https://app.outlay-ai.com/internal/outlay/sync-due  \
  -H "Authorization: Bearer $OUTLAY_CRON_TOKEN"
curl -fsS -X POST https://app.outlay-ai.com/internal/outlay/digest-due \
  -H "Authorization: Bearer $OUTLAY_CRON_TOKEN"
```

Any scheduler works — a Fly scheduled machine, a GitHub Actions `schedule`
workflow, an external cron host, or an uptime service that supports POST.

---

## Verify it's running

- **Operator UI:** sign in as admin → **Scheduler health** (`/admin/health`).
  Each job shows last run / age / last result, with a red banner if a job is
  overdue (no run in > 36h).
- **Machine-readable:** `GET /api/health` returns `cron_ok` (a single rollup) and
  per-job freshness — point an uptime monitor at it and alert when `cron_ok` is
  `false`.

```bash
curl -s https://app.outlay-ai.com/api/health | jq '{cron_ok, cron}'
```

If a job is stale: confirm the env vars are set (in-process) **or** that your
external scheduler is still POSTing with the right `OUTLAY_CRON_TOKEN`.
