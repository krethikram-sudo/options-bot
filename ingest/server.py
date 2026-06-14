"""ModelPilot telemetry ingest — the vendor-side receiver for opt-in,
aggregate-only customer telemetry (see modelpilot/telemetry.py).

INTERNAL: this runs on OUR infrastructure, not the customer's. It is not part of
the shipped `modelpilot` package and is not migrated to the customer repo.

What it does:
  POST /ingest   — accept a telemetry payload, REJECT anything that looks like it
                   carries sensitive data (defense in depth — the client already
                   guarantees aggregates only; we refuse to store otherwise), and
                   store the raw aggregate JSON.
  GET  /agg      — cross-deployment rollup that directly informs product tuning:
                   mean catch-all rate, per-category incident rates + volume, and
                   the top catch-all phrase signals summed across deployments.
  GET  /health   — liveness.

Run:
  pip install fastapi uvicorn
  python -m ingest.server          # or: uvicorn ingest.server:app --port 8500
Env: INGEST_DB (default ingest.db).
"""

import json
import os
import sqlite3
import time
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request

# Keys that must NEVER appear in an aggregate telemetry payload. If any show up
# (at any nesting), we refuse the payload rather than risk storing sensitive data.
_FORBIDDEN_KEYS = {
    "messages", "prompt", "prompts", "content", "text", "output", "outputs",
    "completion", "api_key", "apikey", "x-api-key", "authorization", "secret",
    "example", "examples", "baseline_text", "routed_text",
}

_DB = os.environ.get("INGEST_DB", "ingest.db")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS payloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    deployment_id TEXT,
    version TEXT,
    raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payloads_dep ON payloads (deployment_id);
"""


def _conn():
    c = sqlite3.connect(_DB)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def _forbidden_path(obj, path=""):
    """Return the first forbidden key path found, or None. Defense in depth."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in _FORBIDDEN_KEYS:
                return f"{path}.{k}".lstrip(".")
            hit = _forbidden_path(v, f"{path}.{k}")
            if hit:
                return hit
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hit = _forbidden_path(v, f"{path}[{i}]")
            if hit:
                return hit
    return None


app = FastAPI(title="ModelPilot telemetry ingest")


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/ingest")
async def ingest(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "body must be JSON")
    if not isinstance(payload, dict):
        raise HTTPException(400, "payload must be a JSON object")
    bad = _forbidden_path(payload)
    if bad is not None:
        # Refuse — we never want to be the place sensitive data leaked to.
        raise HTTPException(422, f"rejected: payload contains a forbidden key '{bad}' "
                                 "(telemetry must be aggregates only)")
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO payloads (ts, deployment_id, version, raw) VALUES (?,?,?,?)",
            (time.time(), str(payload.get("deployment_id") or ""),
             str(payload.get("modelpilot_version") or ""), json.dumps(payload)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.get("/agg")
async def agg(since_days: float = 30.0):
    """Latest payload per deployment, rolled up for product tuning."""
    since = time.time() - since_days * 86_400 if since_days else 0.0
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT deployment_id, raw, ts FROM payloads WHERE ts >= ? ORDER BY ts",
            (since,),
        ).fetchall()
    finally:
        conn.close()

    latest = {}  # one (the most recent) payload per deployment
    for r in rows:
        latest[r["deployment_id"]] = json.loads(r["raw"])
    deployments = list(latest.values())
    if not deployments:
        return {"n_deployments": 0}

    catch_rates = [d.get("catch_all_rate", 0.0) for d in deployments]
    total_requests = sum(d.get("n_requests", 0) for d in deployments)
    cat_n = defaultdict(int)
    cat_incidents = defaultdict(float)   # n-weighted incident rate accumulator
    cat_applied = defaultdict(int)
    phrase_docs = defaultdict(int)
    for d in deployments:
        for c in d.get("by_category", []):
            cat_n[c["category"]] += c.get("n", 0)
            cat_applied[c["category"]] += c.get("n_applied", 0)
            cat_incidents[c["category"]] += (c.get("incident_rate", 0.0) or 0.0) * (c.get("n_applied", 0) or 0)
        for p in d.get("catchall_phrase_signals", []):
            phrase_docs[p["phrase"]] += p.get("docs", 0)

    per_category = sorted((
        {"category": cat, "total_n": cat_n[cat],
         "incident_rate": round(cat_incidents[cat] / cat_applied[cat], 3) if cat_applied[cat] else 0.0}
        for cat in cat_n
    ), key=lambda c: -c["total_n"])
    top_phrases = sorted(
        ({"phrase": p, "docs": n} for p, n in phrase_docs.items()),
        key=lambda x: -x["docs"])[:30]

    return {
        "n_deployments": len(deployments),
        "total_requests": total_requests,
        "mean_catch_all_rate": round(sum(catch_rates) / len(catch_rates), 3),
        "per_category": per_category,
        "top_catchall_phrases": top_phrases,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ingest.server:app", host="127.0.0.1",
                port=int(os.environ.get("INGEST_PORT", "8500")), log_level="warning")
