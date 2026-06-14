"""Opt-in request logs — per-request METADATA only (never prompt text), shipped
to the ModelPilot console and/or exported to your own OTLP endpoint.

This is observability without shipping us your prompts: each row is timestamps,
models, category, token counts, dollars, status, routed/escalated flags — the
content stays on your box. Off unless MODELPILOT_LOGS=1 (console) and/or
MODELPILOT_OTEL_ENDPOINT is set (your collector).

Incremental + restart-safe via a rowid marker file next to the ledger.
"""

import json
import os

# Metadata fields shipped per request. Deliberately excludes prompt/rationale.
_FIELDS = ("ts", "category", "original_model", "routed_model", "applied", "action",
           "status_code", "input_tokens", "output_tokens", "cache_read_tokens",
           "cache_write_tokens", "actual_cost", "baseline_cost", "realized_saved",
           "arm", "is_retry")


def _marker_path(db_path: str) -> str:
    return (db_path or "modelpilot.db") + ".logs_marker"


def _read_marker(db_path: str) -> int:
    try:
        with open(_marker_path(db_path)) as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def _write_marker(db_path: str, rowid: int) -> None:
    try:
        with open(_marker_path(db_path), "w") as f:
            f.write(str(rowid))
    except OSError:
        pass


def _clean(row: dict) -> dict:
    out = {k: row.get(k) for k in _FIELDS}
    out["applied"] = bool(row.get("applied"))
    out["escalated"] = bool(row.get("is_retry"))
    out.pop("is_retry", None)
    return out


# --------------------------------------------------------------------------- #
# OTLP/HTTP (JSON) trace export — to YOUR collector, no deps
# --------------------------------------------------------------------------- #

def _attr(k, v):
    if isinstance(v, bool):
        return {"key": k, "value": {"boolValue": v}}
    if isinstance(v, int):
        return {"key": k, "value": {"intValue": v}}
    if isinstance(v, float):
        return {"key": k, "value": {"doubleValue": v}}
    return {"key": k, "value": {"stringValue": "" if v is None else str(v)}}


def otlp_payload(rows: list[dict]) -> dict:
    """Build an OTLP/HTTP JSON traces payload — one span per request, attributes
    are metadata only. Accepted by standard OTLP collectors."""
    import secrets
    spans = []
    for r in rows:
        ts_ns = int(float(r.get("ts") or 0) * 1e9)
        spans.append({
            "traceId": secrets.token_hex(16), "spanId": secrets.token_hex(8),
            "name": f"modelpilot.route:{r.get('category', 'unknown')}",
            "kind": 3,  # CLIENT
            "startTimeUnixNano": str(ts_ns), "endTimeUnixNano": str(ts_ns),
            "attributes": [_attr(f"modelpilot.{k}", v) for k, v in r.items()],
        })
    return {"resourceSpans": [{
        "resource": {"attributes": [_attr("service.name", "modelpilot")]},
        "scopeSpans": [{"scope": {"name": "modelpilot"}, "spans": spans}],
    }]}


def export_otlp(rows: list[dict], endpoint: str, post_fn=None) -> bool:
    if not rows or not endpoint:
        return False
    payload = otlp_payload(rows)
    if post_fn is not None:
        post_fn(payload)
        return True
    import httpx
    r = httpx.post(endpoint.rstrip("/"), json=payload, timeout=5.0,
                   headers={"content-type": "application/json"})
    r.raise_for_status()
    return True


# --------------------------------------------------------------------------- #
# Ship a batch (console + optional OTLP), advance the marker
# --------------------------------------------------------------------------- #

def ship_once(db_path: str | None = None, console_url: str | None = None,
              deployment_id: str | None = None, otel_endpoint: str | None = None,
              batch: int = 500, post_fn=None, otel_post_fn=None) -> dict:
    """Read new ledger rows (metadata only), POST them to the console's /api/logs
    and/or export OTLP to your collector, then advance the marker. Best-effort."""
    db_path = db_path or os.environ.get("MODELPILOT_DB", "modelpilot.db")
    console_url = (console_url or os.environ.get("MODELPILOT_CONSOLE_URL", "")).rstrip("/")
    deployment_id = deployment_id or os.environ.get("MODELPILOT_DEPLOYMENT_ID", "")
    otel_endpoint = otel_endpoint or os.environ.get("MODELPILOT_OTEL_ENDPOINT", "")
    if not (console_url or otel_endpoint):
        return {"shipped": 0, "reason": "no console url / otel endpoint"}

    from .ledger import Ledger
    ledger = Ledger(db_path)
    try:
        raw = ledger.rows_since(_read_marker(db_path), batch)
    finally:
        ledger.close()
    if not raw:
        return {"shipped": 0, "reason": "nothing new"}
    last_rowid = raw[-1]["_rowid"]
    rows = [_clean(r) for r in raw]

    sent_console = sent_otel = False
    if console_url and deployment_id:
        try:
            if post_fn is not None:
                post_fn({"deployment_id": deployment_id, "logs": rows})
            else:
                import httpx
                headers = {}
                key = os.environ.get("MODELPILOT_API_KEY")
                if key:
                    headers["Authorization"] = f"Bearer {key}"
                resp = httpx.post(f"{console_url}/api/logs",
                                  json={"deployment_id": deployment_id, "logs": rows},
                                  timeout=5.0, headers=headers)
                resp.raise_for_status()
            sent_console = True
        except Exception as e:  # noqa: BLE001 — logging must never break the gateway
            return {"shipped": 0, "reason": f"console post failed: {e}"}
    if otel_endpoint:
        try:
            sent_otel = export_otlp(rows, otel_endpoint, otel_post_fn)
        except Exception:  # noqa: BLE001
            sent_otel = False

    # Advance only if at least one sink accepted the batch.
    if sent_console or sent_otel:
        _write_marker(db_path, last_rowid)
    return {"shipped": len(rows), "console": sent_console, "otel": sent_otel}


def main():
    import argparse
    import time
    p = argparse.ArgumentParser(prog="modelpilot logs",
                                description="ship opt-in per-request metadata logs (console + OTLP)")
    p.add_argument("--db", default=os.environ.get("MODELPILOT_DB", "modelpilot.db"))
    p.add_argument("--console-url", default=os.environ.get("MODELPILOT_CONSOLE_URL", ""))
    p.add_argument("--deployment-id", default=os.environ.get("MODELPILOT_DEPLOYMENT_ID", ""))
    p.add_argument("--otel-endpoint", default=os.environ.get("MODELPILOT_OTEL_ENDPOINT", ""))
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=60)
    a = p.parse_args()
    while True:
        print(json.dumps(ship_once(a.db, a.console_url, a.deployment_id, a.otel_endpoint)))
        if not a.watch:
            return
        time.sleep(max(5, a.interval))


if __name__ == "__main__":
    main()
