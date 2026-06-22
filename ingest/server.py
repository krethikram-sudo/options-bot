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
import re
import sqlite3
import time
from collections import defaultdict

import html

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

# Keys that must NEVER appear in an aggregate telemetry payload. If any show up
# (at any nesting), we refuse the payload rather than risk storing sensitive data.
_FORBIDDEN_KEYS = {
    "messages", "prompt", "prompts", "content", "text", "output", "outputs",
    "completion", "api_key", "apikey", "x-api-key", "authorization", "secret",
    "example", "examples", "baseline_text", "routed_text",
}

# Value-level scan: refuse a payload whose string VALUES look like a credential, so a
# secret slipped under an unlisted field name is still caught (not just key-name match).
_SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{12,}|AIza[0-9A-Za-z_-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}"
    r"|[Bb]earer\s+[A-Za-z0-9._-]{16,})")

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
    """Return the first forbidden key path / credential-looking value found, or None.
    Defense in depth — matches both sensitive key NAMES and secret-looking VALUES."""
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
    elif isinstance(obj, str) and _SECRET_VALUE_RE.search(obj):
        return f"{path}=<credential-like value>".lstrip(".")
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


def _rollup(since_days: float = 30.0) -> dict:
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
        {"category": cat, "total_n": cat_n[cat], "applied": cat_applied[cat],
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


@app.get("/agg")
async def agg(since_days: float = 30.0):
    return _rollup(since_days)


# Hard categories we never auto-suggest loosening (quality must stay strong).
_HARD = {"debugging", "math_logic", "codegen_complex", "agentic",
         "analysis_strategy", "creative_longform", "unknown", "conversation"}
# phrase keyword -> (starter pack, suggested category)
_PHRASE_TARGETS = [
    (("invoice", "receipt", "extract", "parse", "table", "field", "ocr", "spreadsheet", "rows", "column"),
     "doc-extraction", "extraction"),
    (("ticket", "reply", "support", "compliance", "refund", "pass/fail", "triage"),
     "support", "classification"),
    (("contract", "clause", "redline", "nda", "agreement", "governing law", "lease"),
     "legal", "extraction"),
    (("chart", "icd", "clinical", "prior auth", "cpt", "patient", "ehr", "payer"),
     "healthcare", "extraction"),
    (("function", "script", "regex", "sql", "endpoint", "component", "docstring", "migration"),
     "coding", "codegen_simple"),
]


def _target_for(phrase: str):
    low = phrase.lower()
    for keys, pack, cat in _PHRASE_TARGETS:
        if any(k in low for k in keys):
            return pack, cat
    return None, None


def _suggestions(agg: dict) -> list[dict]:
    """Turn the rollup into prioritized, concrete tuning actions."""
    if not agg.get("n_deployments"):
        return []
    out = []
    car = agg["mean_catch_all_rate"]
    if car >= 0.15:
        out.append({"priority": "high" if car >= 0.30 else "medium",
                    "action": "Run a router-recall pass / ship segment rule-packs",
                    "why": f"fleet mean catch-all rate is {car:.0%} — that much traffic stays on the baseline"})
    for c in agg["per_category"]:
        cat, n, ir, ap = c["category"], c["total_n"], c["incident_rate"], c.get("applied", 0)
        if ir > 0.02 and ap >= 20:
            out.append({"priority": "high", "action": f"Tighten `{cat}` (raise its gate/floor)",
                        "why": f"{ir:.1%} incident rate over {ap} applied routes (>2% target)"})
        elif ir == 0 and n >= 50 and cat not in _HARD:
            out.append({"priority": "medium", "action": f"Loosen `{cat}` (lower its floor/gate)",
                        "why": f"{n:,} fleet requests, 0 incidents — proven safe; capture more savings"})
    for p in agg["top_catchall_phrases"][:8]:
        pack, cat = _target_for(p["phrase"])
        if pack:
            out.append({"priority": "medium",
                        "action": f'Add "{p["phrase"]}" → {cat} (the {pack} pack / global recall)',
                        "why": f"recurring catch-all phrase across {p['docs']} prompts"})
        else:
            out.append({"priority": "low",
                        "action": f'Review "{p["phrase"]}" for a new rule / recall pattern',
                        "why": f"recurring catch-all phrase across {p['docs']} prompts; no obvious segment match"})
    rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda a: rank[a["priority"]])
    return out


@app.get("/actions")
async def actions(since_days: float = 30.0):
    return {"actions": _suggestions(_rollup(since_days))}


def _render(agg: dict) -> str:
    e = html.escape
    if not agg.get("n_deployments"):
        return ("<!doctype html><meta charset=utf-8><title>ModelPilot fleet</title>"
                "<body style='font:15px -apple-system,sans-serif;margin:3rem;color:#1f2430'>"
                "<h1>ModelPilot fleet telemetry</h1><p>No telemetry received yet.</p></body>")
    cards = (
        f"<div class=card><div class=num>{agg['n_deployments']}</div><div class=lbl>deployments reporting</div></div>"
        f"<div class=card><div class=num>{agg['total_requests']:,}</div><div class=lbl>requests scored</div></div>"
        f"<div class=card><div class=num>{agg['mean_catch_all_rate']:.0%}</div>"
        "<div class=lbl>mean catch-all rate (blind spot)</div></div>"
    )
    # per-category rows with inline bars
    maxn = max((c["total_n"] for c in agg["per_category"]), default=1) or 1
    catrows = ""
    for c in agg["per_category"]:
        barw = int(100 * c["total_n"] / maxn)
        risk = "bad" if c["incident_rate"] > 0.02 else "ok"
        catrows += (
            f"<tr><td>{e(c['category'])}</td>"
            f"<td><div class=bar><span style='width:{barw}%'></span></div>{c['total_n']:,}</td>"
            f"<td class={risk}>{c['incident_rate']:.1%}</td></tr>"
        )
    # Suggested actions panel
    _pri_color = {"high": "#b3372f", "medium": "#2f6fb6", "low": "#6b7080"}
    sugg = _suggestions(agg)
    if sugg:
        items = "".join(
            f'<li><b style="color:{_pri_color[s["priority"]]}">[{s["priority"]}]</b> '
            f'{e(s["action"])}<br><span class=muted style="font-size:.82rem">{e(s["why"])}</span></li>'
            for s in sugg)
        actions_html = (f'<div class="actions"><h2 style="font-size:1.05rem;margin:.2rem 0 .6rem">'
                        f'Suggested actions ({len(sugg)})</h2><ul>{items}</ul></div>')
    else:
        actions_html = ""

    maxd = max((p["docs"] for p in agg["top_catchall_phrases"]), default=1) or 1
    phraserows = "".join(
        f"<tr><td>{e(p['phrase'])}</td><td><div class=bar><span style='width:{int(100*p['docs']/maxd)}%'></span></div>"
        f"{p['docs']}</td></tr>"
        for p in agg["top_catchall_phrases"]
    ) or "<tr><td colspan=2 class=muted>No phrase signals (customers haven't shared --with-phrases).</td></tr>"

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>ModelPilot fleet telemetry</title><style>
 body{{font:15px/1.5 -apple-system,"Segoe UI",sans-serif;color:#1f2430;margin:2rem auto;max-width:900px;padding:0 1rem}}
 h1{{font-size:1.4rem}} .muted{{color:#6b7080}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap;margin:1rem 0}}
 .card{{border:1px solid #e3e3e8;border-radius:10px;padding:12px 16px;min-width:170px}}
 .num{{font-size:1.6rem;font-weight:700}} .lbl{{color:#6b7080;font-size:.82rem}}
 table{{border-collapse:collapse;width:100%;font-size:.9rem;margin:.4rem 0 1.6rem}}
 td,th{{border-bottom:1px solid #eee;padding:7px 10px;text-align:left}} th{{color:#6b7080}}
 .bar{{display:inline-block;width:120px;height:8px;background:#f0f0f3;border-radius:4px;margin-right:8px;vertical-align:middle}}
 .bar span{{display:block;height:8px;background:#2f6fb6;border-radius:4px}}
 .ok{{color:#2e9e5b}} .bad{{color:#b3372f;font-weight:600}}
 .actions{{border:1px solid #d8e4f0;background:#f6f9fc;border-radius:10px;padding:10px 16px;margin:1rem 0}}
 .actions ul{{margin:.2rem 0;padding-left:1.1rem}} .actions li{{margin:.4rem 0}}
</style></head><body>
<h1>ModelPilot fleet telemetry</h1>
<p class="muted">Aggregate, opt-in metrics across customer deployments — no prompt text.
Drives the next router-recall pass, floor/gate tuning, and starter-pack updates.</p>
<div class="cards">{cards}</div>
{actions_html}
<h2 style="font-size:1.05rem">By category — volume &amp; incident rate</h2>
<p class="muted" style="font-size:.82rem">High volume + low incident rate = loosen (more savings). Incident rate &gt;2% (red) = tighten.</p>
<table><tr><th>category</th><th>requests (across fleet)</th><th>incident rate</th></tr>{catrows}</table>
<h2 style="font-size:1.05rem">Top catch-all phrase signals</h2>
<p class="muted" style="font-size:.82rem">k-anonymous recurring phrasings that landed in catch-alls — recall/rule-pack candidates.</p>
<table><tr><th>phrase</th><th>distinct prompts (summed)</th></tr>{phraserows}</table>
</body></html>"""


@app.get("/dashboard")
async def dashboard(since_days: float = 30.0):
    return HTMLResponse(_render(_rollup(since_days)))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ingest.server:app", host="127.0.0.1",
                port=int(os.environ.get("INGEST_PORT", "8500")), log_level="warning")
