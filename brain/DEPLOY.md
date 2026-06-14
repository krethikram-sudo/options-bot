# Deploying the ModelPilot backend (brain + ingest) — VENDOR / INTERNAL

Two small stateless-ish services you host. Customers point their gateway at them
via two env vars. Both have Dockerfiles (build from the **repo root**) and need a
small persistent volume mounted at `/data` (SQLite: trial clock / telemetry).

| Service | Purpose | Port | Persists at /data | Client env var |
|---|---|---|---|---|
| **brain** (`brain/`) | routing decision + license/7-day-trial enforcement | 8600 | `brain.db` (trial clock) | `MODELPILOT_BRAIN_URL` |
| **ingest** (`ingest/`) | receive + roll up opt-in aggregate telemetry | 8500 | `ingest.db` | `MODELPILOT_TELEMETRY_URL` |

## Build & run locally
```bash
docker build -f brain/Dockerfile  -t modelpilot-brain  .
docker build -f ingest/Dockerfile -t modelpilot-ingest .
docker run -p 8600:8600 -v $PWD/braindata:/data  modelpilot-brain
docker run -p 8500:8500 -v $PWD/ingestdata:/data modelpilot-ingest
# health:
curl localhost:8600/health && curl localhost:8500/health
```

## Deploy to a host (Fly.io example — free-tier friendly)
```bash
# brain
fly launch --no-deploy --name modelpilot-brain --dockerfile brain/Dockerfile
fly volumes create data --size 1 -a modelpilot-brain     # mounts at /data
fly deploy -a modelpilot-brain                            # -> https://modelpilot-brain.fly.dev
# ingest (repeat)
fly launch --no-deploy --name modelpilot-ingest --dockerfile ingest/Dockerfile
fly volumes create data --size 1 -a modelpilot-ingest
fly deploy -a modelpilot-ingest                           # -> https://modelpilot-ingest.fly.dev
```
(Render / Railway / a plain VM work the same way: build the Dockerfile, mount a
volume at `/data`, expose the port.) In `fly.toml` set the mount to `/data` and
`internal_port` to 8600 / 8500.

## Point customers at them
Give trial/customer deployments:
```bash
export MODELPILOT_BRAIN_URL=https://modelpilot-brain.fly.dev
export MODELPILOT_TELEMETRY_URL=https://modelpilot-ingest.fly.dev/ingest   # opt-in only
modelpilot gateway --mode autopilot --port 8400
```
With `MODELPILOT_BRAIN_URL` set, the gateway gets every routing decision from the
brain and the brain enforces entitlement (license, else server-tracked 7-day
trial). If the brain is unreachable, the gateway **fails open** to local routing —
customer traffic is never blocked.

## Wire to the console (accounts + mode)
Set `CONSOLE_URL=https://app.modelpilot.app` on the brain and it reads entitlement
+ routing mode from the console (the customer's account + dashboard toggle):
entitled while on trial/paid, and auto-applies decisions only in **autopilot**
mode. Without `CONSOLE_URL` the brain uses its own license/7-day-trial path. See
`console/DEPLOY.md`.

## Security / privacy notes
- The brain verifies licenses with the **bundled public key**; the **private key
  never goes in the image** (issue tokens with `python -m modelpilot.license issue`
  on your own machine). Put it behind HTTPS.
- The brain and ingest both **reject any request containing prompts/outputs/keys**
  (422) — defense in depth; only category labels + numeric features + aggregates
  ever arrive.
- Trial enforcement is now **server-authoritative** (brain `brain.db`), so it can't
  be reset by editing the client.
