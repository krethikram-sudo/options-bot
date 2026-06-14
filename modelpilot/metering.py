"""Usage metering: report realized savings from the local ledger to the hosted
ModelPilot console, so billing reflects the savings actually delivered.

Privacy: aggregate dollars + counts ONLY — never prompt text, outputs, or keys
(the console also rejects any payload that looks like it carries those). Reports
are incremental: a marker file records the last cumulative totals posted, so we
only ever send the delta since the previous report (restart-safe).

Configuration (set on the customer's gateway):
  MODELPILOT_CONSOLE_URL    https://app.modelpilot.app
  MODELPILOT_DEPLOYMENT_ID  dep_...   (issued at signup, shown on the Connect page)
"""

import json
import os

_FIELDS = ("requests", "routed", "baseline_cost", "actual_cost", "realized_savings",
           "comparisons", "non_inferior")


def _marker_path(db_path: str) -> str:
    return (db_path or "modelpilot.db") + ".meter_marker"


def _read_marker(db_path: str) -> dict:
    try:
        with open(_marker_path(db_path)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {k: 0.0 for k in _FIELDS}


def _write_marker(db_path: str, cumulative: dict) -> None:
    try:
        with open(_marker_path(db_path), "w") as f:
            json.dump(cumulative, f)
    except OSError:
        pass


def _cumulative_from_summary(summary: dict, proof: dict | None = None) -> dict:
    proof = proof or {}
    return {
        "requests": float(summary.get("n", 0)),
        "routed": float(summary.get("n_applied", 0)),
        "baseline_cost": float(summary.get("baseline", 0.0)),
        "actual_cost": float(summary.get("actual", 0.0)),
        "realized_savings": float(summary.get("realized", 0.0)),
        # Aggregate side-by-side proof counts (no compared text leaves the box).
        "comparisons": float(proof.get("n_judged", 0)),
        "non_inferior": float(proof.get("n_ni", 0)),
    }


def compute_delta(cumulative: dict, marker: dict) -> dict:
    """Delta since the last report, never negative (a reset ledger -> start fresh)."""
    return {k: max(0.0, cumulative.get(k, 0.0) - marker.get(k, 0.0)) for k in _FIELDS}


def report_once(db_path: str | None = None, console_url: str | None = None,
                deployment_id: str | None = None, post_fn=None) -> dict:
    """Read the ledger, post the savings delta to the console, advance the marker.
    Returns a small status dict. Best-effort: never raises on network failure."""
    db_path = db_path or os.environ.get("MODELPILOT_DB", "modelpilot.db")
    console_url = (console_url or os.environ.get("MODELPILOT_CONSOLE_URL", "")).rstrip("/")
    deployment_id = deployment_id or os.environ.get("MODELPILOT_DEPLOYMENT_ID", "")
    if not console_url or not deployment_id:
        return {"posted": False, "reason": "console url / deployment id not set"}

    from .ledger import Ledger
    ledger = Ledger(db_path)
    try:
        cumulative = _cumulative_from_summary(ledger.summary(), ledger.proof_summary())
    finally:
        ledger.close()
    marker = _read_marker(db_path)
    delta = compute_delta(cumulative, marker)
    if delta["requests"] <= 0 and delta["realized_savings"] <= 0 and delta["comparisons"] <= 0:
        return {"posted": False, "reason": "nothing new", "cumulative": cumulative}

    payload = {"deployment_id": deployment_id,
               "requests": int(delta["requests"]), "routed": int(delta["routed"]),
               "baseline_cost": round(delta["baseline_cost"], 6),
               "actual_cost": round(delta["actual_cost"], 6),
               "realized_savings": round(delta["realized_savings"], 6),
               "comparisons": int(delta["comparisons"]),
               "non_inferior": int(delta["non_inferior"])}
    try:
        if post_fn is not None:
            post_fn(payload)
        else:
            import httpx
            headers = {}
            key = os.environ.get("MODELPILOT_API_KEY")
            if key:
                headers["Authorization"] = f"Bearer {key}"
            r = httpx.post(f"{console_url}/api/meter", json=payload, timeout=5.0, headers=headers)
            r.raise_for_status()
    except Exception as e:  # noqa: BLE001 — metering must never break the gateway
        return {"posted": False, "reason": f"post failed: {e}", "delta": delta}
    _write_marker(db_path, cumulative)
    return {"posted": True, "delta": delta}


def main():
    """`modelpilot meter [--watch] [--interval N]` — one-shot or looping reporter
    (for cron or a sidecar). Uses the same env as the gateway."""
    import argparse
    import time

    p = argparse.ArgumentParser(prog="modelpilot meter",
                                description="report realized savings to the ModelPilot console")
    p.add_argument("--db", default=os.environ.get("MODELPILOT_DB", "modelpilot.db"))
    p.add_argument("--console-url", default=os.environ.get("MODELPILOT_CONSOLE_URL", ""))
    p.add_argument("--deployment-id", default=os.environ.get("MODELPILOT_DEPLOYMENT_ID", ""))
    p.add_argument("--watch", action="store_true", help="loop forever")
    p.add_argument("--interval", type=int, default=60, help="seconds between reports in --watch")
    a = p.parse_args()
    if not a.console_url or not a.deployment_id:
        raise SystemExit("Set MODELPILOT_CONSOLE_URL and MODELPILOT_DEPLOYMENT_ID "
                         "(or pass --console-url/--deployment-id).")
    while True:
        res = report_once(a.db, a.console_url, a.deployment_id)
        print(json.dumps(res.get("delta", res), default=str))
        if not a.watch:
            return
        time.sleep(max(5, a.interval))


if __name__ == "__main__":
    main()
