"""Outlay MCP server — query attributed AI spend from any MCP client (Claude, Cursor).

Brings Outlay's numbers to where engineers already work — the editor — over the
Model Context Protocol, the same distribution pattern that spread Weave's metrics
plugin. An MCP client (Claude Code, Cursor, etc.) connects to this stdio server and
the model can then *ask Outlay questions in natural language* — "what did the
growth team spend?", "what's our forecast and how accurate is it?", "should we
commit?" — because it has Outlay's tools.

Design constraints (match the rest of the engine):
  * **stdlib only** — a minimal, MCP-compliant newline-delimited JSON-RPC 2.0 stdio
    server. No third-party MCP SDK.
  * **read-only** — every tool reads an attributed report; nothing mutates or routes.
  * **testable** — `handle(request, report)` is pure; `main()` just wires stdio.

The report is the engine's serialized output (`outlay.serialize.to_dict`). By
default the server builds it from the bundled fixtures so it's demoable out of the
box; point it at real data with `OUTLAY_REPORT=/path/to/report.json`.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from typing import Any, Callable

from .units import cost_per_unit

SERVER_NAME = "outlay"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2024-11-05"


# --------------------------------------------------------------------------- #
# Tool implementations — each takes (report, arguments) → a JSON-able result.
# --------------------------------------------------------------------------- #
def _spend(report: dict) -> dict:
    return report.get("spend", {}) or {}


def _tickets(report: dict) -> list[dict]:
    return report.get("tickets", []) or []


def tool_spend_overview(report: dict, args: dict) -> dict:
    s = _spend(report)
    return {
        "total_usd": s.get("total_usd", 0.0),
        "attributed_to_ticket_usd": s.get("attributed_to_ticket_usd", 0.0),
        "ticket_coverage": s.get("ticket_coverage", 0.0),
        "by_fidelity_usd": s.get("by_fidelity_usd", {}),
        "window_days": report.get("window_days"),
        "tickets": len(_tickets(report)),
    }


def tool_cost_drilldown(report: dict, args: dict) -> dict:
    """Group attributed spend by a dimension: team | class | status | ticket."""
    by = (args.get("by") or "team").lower()
    if by not in ("team", "class", "status", "ticket"):
        raise ValueError("`by` must be one of: team, class, status, ticket")
    key = {"team": "team_id", "class": "task_class", "status": "status",
           "ticket": "ticket_id"}[by]
    agg: dict[str, dict] = defaultdict(lambda: {"cost_usd": 0.0, "count": 0})
    for t in _tickets(report):
        k = t.get(key) or "(unassigned)"
        agg[k]["cost_usd"] += t.get("cost_usd", 0.0)
        agg[k]["count"] += 1
    rows = [{by: k, "cost_usd": round(v["cost_usd"], 4), "items": v["count"]}
            for k, v in agg.items()]
    rows.sort(key=lambda r: r["cost_usd"], reverse=True)
    return {"by": by, "rows": rows}


def tool_cost_per_unit(report: dict, args: dict) -> dict:
    return cost_per_unit(report)


def tool_forecast(report: dict, args: dict) -> dict:
    fc = report.get("forecast", {}) or {}
    cal = report.get("calibration", {}) or {}
    return {
        "expected_usd": fc.get("expected_usd", 0.0),
        "low_usd": fc.get("low_usd", 0.0),
        "high_usd": fc.get("high_usd", 0.0),
        "items_costed": fc.get("items_costed", 0),
        "items_unclassified": fc.get("items_unclassified", 0),
        "by_class_usd": fc.get("by_class_usd", {}),
        # Validation — the trust unlock. Back-tested on the customer's own work.
        "backtest": {
            "accuracy": cal.get("accuracy"),
            "mdape": cal.get("mdape"),
            "within_p90": cal.get("within_p90"),
            "n_evaluated": cal.get("n_evaluated"),
            "note": "Leave-one-out back-test on delivered work — measured, not asserted.",
        },
    }


def tool_recommendations(report: dict, args: dict) -> dict:
    """Cheaper-model routing recommendations, net of an assumed rework penalty."""
    return {"recommendations": report.get("recommendations", []) or []}


def tool_commitment_recommendation(report: dict, args: dict) -> dict:
    """Should the customer commit vs stay on-demand? Sizes a committed-spend discount
    from the monthly run-rate implied by the report."""
    from .commitment import decompose, default_ratecard, recommend_commitment

    s = _spend(report)
    total = float(s.get("total_usd", 0.0) or 0.0)
    window = report.get("window_days") or 30
    if total <= 0:
        return {"recommendation": "no spend to evaluate"}
    monthly = total * (30.0 / float(window))
    profile = decompose([monthly])
    card = default_ratecard()
    scen = recommend_commitment(profile, monthly, card, floor_periods=1)
    best = max(scen, key=lambda x: x.net_savings_usd) if scen else None
    return {
        "monthly_run_rate_usd": round(monthly, 2),
        "scenarios": [
            {"label": x.label, "commit_usd": x.commit_usd, "discount": x.discount,
             "net_savings_usd": x.net_savings_usd,
             "effective_savings_rate": x.effective_savings_rate,
             "forfeit_risk": x.forfeit_risk} for x in scen],
        "recommended": (
            {"commit_usd": best.commit_usd, "net_savings_usd": best.net_savings_usd,
             "effective_savings_rate": best.effective_savings_rate}
            if best and best.net_savings_usd > 0 else None),
        "note": "Illustrative tiers — replace with your negotiated terms. Advisory; you commit with the vendor.",
    }


def tool_procurement_mix(report: dict, args: dict) -> dict:
    """The cheapest split of flat-fee seat plans vs. API credits, from per-employee
    spend — seats for the heavy users, API for the light ones."""
    from .planmix import optimize_mix

    people = report.get("people") or []
    window = report.get("window_days") or 30
    to_month = 30.0 / float(window)
    monthly = [{"user": p.get("user"),
                "usage_usd": float(p.get("spent_usd", 0.0) or 0.0) * to_month}
               for p in people]
    if not any(m["user"] and m["user"] != "(unattributed)" and m["usage_usd"] > 0 for m in monthly):
        return {"recommendation": "no per-person spend to optimize (improve attribution coverage)"}
    res = optimize_mix(monthly)
    return {
        "status_quo_all_api_usd": res.status_quo_usd,
        "optimized_usd": res.optimized_usd,
        "total_savings_usd": res.total_savings_usd,
        "savings_rate": res.savings_rate,
        "seats_to_buy": res.seats_by_plan,
        "n_on_api": res.n_on_api,
        "savings_range_usd": [res.savings_low_usd, res.savings_high_usd],
        "note": res.note,
    }


# name -> (handler, description, inputSchema)
TOOLS: dict[str, tuple[Callable[[dict, dict], Any], str, dict]] = {
    "spend_overview": (
        tool_spend_overview,
        "Total attributed AI spend, ticket coverage, and the spend-by-fidelity breakdown.",
        {"type": "object", "properties": {}},
    ),
    "cost_drilldown": (
        tool_cost_drilldown,
        "Group attributed AI spend by a dimension (team, class, status, or ticket).",
        {"type": "object", "properties": {
            "by": {"type": "string", "enum": ["team", "class", "status", "ticket"],
                   "description": "Dimension to group by (default: team)."}}},
    ),
    "cost_per_unit": (
        tool_cost_per_unit,
        "The hero metric: realized AI cost per delivered (shipped) unit of work, overall and per class.",
        {"type": "object", "properties": {}},
    ),
    "forecast": (
        tool_forecast,
        "Backlog AI-spend forecast with its leave-one-out back-test accuracy on delivered work.",
        {"type": "object", "properties": {}},
    ),
    "recommendations": (
        tool_recommendations,
        "Cheaper-model routing recommendations per work class, net of an assumed rework penalty.",
        {"type": "object", "properties": {}},
    ),
    "commitment_recommendation": (
        tool_commitment_recommendation,
        "Whether to take a committed-spend discount vs stay on-demand, sized from the run-rate.",
        {"type": "object", "properties": {}},
    ),
    "procurement_mix": (
        tool_procurement_mix,
        "Cheapest split of flat-fee seat plans vs. API credits from per-employee spend "
        "(seats for heavy users, API for light ones). Illustrative seat terms; advisory.",
        {"type": "object", "properties": {}},
    ),
}


# --------------------------------------------------------------------------- #
# JSON-RPC / MCP protocol
# --------------------------------------------------------------------------- #
def _result(req_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(request: dict, report: dict) -> dict | None:
    """Handle one JSON-RPC request against `report`. Returns the response dict, or
    None for notifications (no `id`) which take no reply. Pure — no I/O."""
    method = request.get("method")
    req_id = request.get("id")
    is_notification = "id" not in request

    if method == "initialize":
        proto = (request.get("params") or {}).get("protocolVersion") or DEFAULT_PROTOCOL
        return _result(req_id, {
            "protocolVersion": proto,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": [
            {"name": name, "description": desc, "inputSchema": schema}
            for name, (_, desc, schema) in TOOLS.items()]})
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        entry = TOOLS.get(name)
        if entry is None:
            return _error(req_id, -32602, f"Unknown tool: {name}")
        handler = entry[0]
        try:
            data = handler(report, args)
        except Exception as e:  # surface tool errors as MCP tool errors, not crashes
            return _result(req_id, {
                "content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})
        return _result(req_id, {
            "content": [{"type": "text", "text": json.dumps(data, indent=2)}]})

    if is_notification:
        return None
    return _error(req_id, -32601, f"Method not found: {method}")


def load_report() -> dict:
    """Load the report to serve: OUTLAY_REPORT path if set, else the bundled demo."""
    path = os.environ.get("OUTLAY_REPORT")
    if path:
        with open(path) as f:
            return json.load(f)
    from pathlib import Path

    from .cli import _FIXTURES, run
    return json.loads(run(_FIXTURES / "anthropic_usage.json", as_json=True, window_days=30))


def main() -> int:
    report = load_report()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_error(None, -32700, "Parse error")) + "\n")
            sys.stdout.flush()
            continue
        response = handle(request, report)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
