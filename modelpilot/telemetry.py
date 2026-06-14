"""Privacy-safe performance telemetry — aggregates only, opt-in, previewable.

How to learn how the product performs in the field WITHOUT collecting anything
sensitive. Hard guarantees:

  - NEVER includes prompt text, model outputs, API keys, or per-request rows.
  - Only LOCAL AGGREGATES leave: per-category counts/rates, routing + quality
    distributions, savings totals, version/env, and an anonymous deployment id.
  - Numbers are coarsened (rounded) so they can't fingerprint a single request.
  - Off by default. The customer runs it explicitly and can `--preview` the exact
    JSON before anything is sent.
  - Optional `--with-phrases` adds catch-all n-gram SIGNALS (e.g. "parse table")
    to guide router recall — but only phrases seen in >= MIN_DOCS *distinct*
    prompts (k-anonymity), stopworded, with NO example text. Requires that the
    customer had prompt-capture on; otherwise it's empty.

    modelpilot telemetry --preview                 # see exactly what would send
    modelpilot telemetry --url https://t.example/ingest      # opt-in upload
    MODELPILOT_TELEMETRY_URL=... modelpilot telemetry         # same via env
    modelpilot telemetry --with-phrases --preview  # include k-anon phrase signals
"""

import argparse
import json
import os
import platform
import time
import uuid

from . import __version__
from .ledger import Ledger

SCHEMA = 3
PHRASE_MIN_DOCS = 5   # k-anonymity floor for shared phrase signals
PHRASE_CAP = 40       # max phrases shared


def _deployment_id(db_path: str) -> str:
    """Stable anonymous id per deployment (random UUID in a sidecar file).
    Not derived from hostname/keys — it identifies a deployment, not a person."""
    side = (db_path or "modelpilot.db") + ".deployment"
    try:
        with open(side) as f:
            return f.read().strip()
    except OSError:
        did = uuid.uuid4().hex
        try:
            with open(side, "w") as f:
                f.write(did)
        except OSError:
            pass
        return did


def _round(x, n=2):
    return round(float(x), n) if x is not None else None


def build_payload(db_path: str, days: float = 30.0, gate: float = 0.7,
                  with_phrases: bool = False, min_docs: int = PHRASE_MIN_DOCS) -> dict:
    ledger = Ledger(db_path)
    try:
        since = time.time() - days * 86_400 if days else 0.0
        s = ledger.summary(since, gate=gate)
        cats = ledger.by_category(since)
        quality = ledger.category_quality(since)
        esc = ledger.escalation_costs(since)
        arms = ledger.arm_costs(since)
        guards = {g["arm"]: g for g in ledger.quality_guardrails(since)}
        captures = ledger.captures(since) if with_phrases else []
    finally:
        ledger.close()

    n = s["n"] or 0
    qmap = {q["category"]: q for q in quality}
    by_category = []
    catchall_n = 0
    for c in cats:
        cat = c["category"]
        if cat in ("conversation", "unknown"):
            catchall_n += c["n"]
        q = qmap.get(cat, {})
        applied = q.get("n_applied", 0) or 0
        incidents = (q.get("n_escalation", 0) or 0) + (q.get("n_negative", 0) or 0)
        by_category.append({
            "category": cat,
            "n": c["n"],
            "avg_confidence": _round(c.get("avg_confidence"), 2),
            "est_savings_usd": _round(c.get("potential"), 2),
            "n_applied": applied,
            "incident_rate": _round(incidents / applied, 3) if applied else 0.0,
        })

    # Holdout quality verdict (aggregate rates only).
    qver = None
    gt, gc = guards.get("treatment", {}), guards.get("control", {})
    if (gt.get("n") or 0) >= 30 and (gc.get("n") or 0) >= 30:
        qver = {
            "neg_rate_routed": _round(gt.get("n_negative", 0) / gt["n"], 3),
            "neg_rate_control": _round(gc.get("n_negative", 0) / gc["n"], 3),
            "treatment_n": gt["n"], "control_n": gc["n"],
        }

    payload = {
        "schema": SCHEMA,
        "deployment_id": _deployment_id(db_path),
        "modelpilot_version": __version__,
        "python": platform.python_version(),
        "os": platform.system(),
        "window_days": days,
        "n_requests": n,
        "n_switch_recs": s.get("n_switch_recs", 0),
        "n_applied": s.get("n_applied", 0),
        "catch_all_rate": _round(catchall_n / n, 3) if n else 0.0,
        "savings": {
            "baseline_usd": _round(s.get("baseline")),
            "realized_usd": _round(s.get("realized")),
            "potential_usd": _round(s.get("potential")),
            "gated_potential_usd": _round(s.get("gated_potential")),
        },
        "escalations": {"n": esc.get("n", 0), "cost_usd": _round(esc.get("cost"))},
        "quality_holdout": qver,
        "by_category": by_category,
        "_privacy": "aggregates only — no prompt text, outputs, or keys",
    }

    if with_phrases and captures:
        from .learn_rules import mine_clusters
        clusters = mine_clusters(captures, min_docs=min_docs, top=PHRASE_CAP)
        # SHARE ONLY phrase + doc count (k-anonymous). Drop the example snippet.
        payload["catchall_phrase_signals"] = [
            {"phrase": c["phrase"], "docs": c["docs"]} for c in clusters
        ]
    return payload


def send(url: str, payload: dict) -> int:
    import httpx
    r = httpx.post(url, json=payload, timeout=10.0)
    r.raise_for_status()
    return r.status_code


def main():
    ap = argparse.ArgumentParser(description="Privacy-safe performance telemetry (opt-in, aggregates only)")
    ap.add_argument("--db", default=os.environ.get("MODELPILOT_DB", "modelpilot.db"))
    ap.add_argument("--days", type=float, default=30.0, help="window (0 = all time)")
    ap.add_argument("--gate", type=float, default=float(os.environ.get("MODELPILOT_CONFIDENCE", "0.7")))
    ap.add_argument("--url", default=os.environ.get("MODELPILOT_TELEMETRY_URL", ""),
                    help="POST the payload here (opt-in). Omit to only preview/print.")
    ap.add_argument("--with-phrases", action="store_true",
                    help="include k-anonymous catch-all phrase signals (needs prior prompt capture)")
    ap.add_argument("--min-docs", type=int, default=PHRASE_MIN_DOCS,
                    help="k-anonymity floor: a phrase must appear in >= this many distinct prompts")
    ap.add_argument("--preview", action="store_true", help="print the exact payload; do not send")
    args = ap.parse_args()

    payload = build_payload(args.db, args.days, args.gate, args.with_phrases, args.min_docs)
    if args.preview or not args.url:
        print(json.dumps(payload, indent=2))
        if not args.url:
            print("\n# No --url / MODELPILOT_TELEMETRY_URL set — nothing was sent (preview only).")
        return
    print(json.dumps(payload, indent=2))
    try:
        code = send(args.url, payload)
        print(f"\nSent to {args.url} (HTTP {code}).")
    except Exception as e:  # noqa: BLE001 — never crash a cron over a delivery hiccup
        print(f"\nSend failed: {e}")


if __name__ == "__main__":
    main()
