"""Outlay MCP server — protocol handshake, tool listing, and tool calls."""

import json

from outlay.mcp_server import TOOLS, cost_per_unit, handle, load_report

# A small attributed report stand-in.
REPORT = {
    "window_days": 30,
    "spend": {"total_usd": 100.0, "attributed_to_ticket_usd": 90.0, "ticket_coverage": 0.9,
              "by_fidelity_usd": {"call": 50.0, "team": 40.0, "invoice": 10.0}},
    "tickets": [
        {"ticket_id": "GH-1", "task_class": "feature", "status": "done", "cost_usd": 40.0, "team_id": "platform"},
        {"ticket_id": "GH-2", "task_class": "bugfix", "status": "done", "cost_usd": 20.0, "team_id": "growth"},
        {"ticket_id": "GH-3", "task_class": "feature", "status": "open", "cost_usd": 30.0, "team_id": "platform"},
    ],
    "forecast": {"expected_usd": 120.0, "low_usd": 90.0, "high_usd": 160.0, "items_costed": 5,
                 "items_unclassified": 1, "by_class_usd": {"feature": 80.0}},
    "calibration": {"accuracy": 0.8, "mdape": 0.18, "within_p90": 0.9, "n_evaluated": 6},
    "recommendations": [{"task_class": "feature", "incumbent_model": "claude-opus-4-8",
                         "candidate_model": "claude-sonnet-4-6", "projected_savings_usd": 12.0,
                         "confidence": "needs_validation"}],
}


def _req(method, params=None, rid=1):
    r = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        r["params"] = params
    return r


# --------------------------- protocol -------------------------------------- #
def test_initialize_handshake():
    resp = handle(_req("initialize", {"protocolVersion": "2025-06-18"}), REPORT)
    assert resp["result"]["serverInfo"]["name"] == "outlay"
    assert resp["result"]["protocolVersion"] == "2025-06-18"
    assert "tools" in resp["result"]["capabilities"]


def test_initialized_notification_no_reply():
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, REPORT) is None


def test_tools_list_matches_registry():
    resp = handle(_req("tools/list"), REPORT)
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == set(TOOLS)
    for t in resp["result"]["tools"]:
        assert t["description"] and t["inputSchema"]["type"] == "object"


def test_unknown_method_errors():
    resp = handle(_req("does/not/exist"), REPORT)
    assert resp["error"]["code"] == -32601


# --------------------------- tool calls ------------------------------------ #
def _call(name, arguments=None):
    return handle(_req("tools/call", {"name": name, "arguments": arguments or {}}), REPORT)


def _payload(resp):
    return json.loads(resp["result"]["content"][0]["text"])


def test_spend_overview():
    d = _payload(_call("spend_overview"))
    assert d["total_usd"] == 100.0 and d["ticket_coverage"] == 0.9 and d["tickets"] == 3


def test_cost_drilldown_by_team_sorted():
    d = _payload(_call("cost_drilldown", {"by": "team"}))
    assert d["by"] == "team"
    assert d["rows"][0]["team"] == "platform"  # 40+30 > 20
    assert d["rows"][0]["cost_usd"] == 70.0


def test_cost_drilldown_rejects_bad_dimension():
    resp = _call("cost_drilldown", {"by": "galaxy"})
    assert resp["result"]["isError"] is True


def test_cost_per_unit_uses_only_shipped():
    d = _payload(_call("cost_per_unit"))
    # Only the two 'done' tickets count: (40+20)/2 = 30.
    assert d["units_shipped"] == 2
    assert d["cost_per_unit_usd"] == 30.0
    assert {r["task_class"] for r in d["by_class"]} == {"feature", "bugfix"}


def test_cost_per_unit_helper_direct():
    assert cost_per_unit(REPORT)["cost_per_unit_usd"] == 30.0


def test_forecast_includes_backtest():
    d = _payload(_call("forecast"))
    assert d["expected_usd"] == 120.0
    assert d["backtest"]["mdape"] == 0.18 and d["backtest"]["n_evaluated"] == 6


def test_recommendations_passthrough():
    d = _payload(_call("recommendations"))
    assert d["recommendations"][0]["candidate_model"] == "claude-sonnet-4-6"


def test_commitment_recommendation_runs():
    d = _payload(_call("commitment_recommendation"))
    assert d["monthly_run_rate_usd"] == 100.0
    assert "scenarios" in d


def test_procurement_mix_tool():
    # A report with per-person spend → the tool recommends seats for the heavy user.
    rep = dict(REPORT, people=[{"user": "eng@acme.dev", "spent_usd": 600.0},
                               {"user": "hr@acme.dev", "spent_usd": 8.0}])
    d = _payload(handle(_req("tools/call", {"name": "procurement_mix", "arguments": {}}), rep))
    assert d["total_savings_usd"] > 0
    assert d["seats_to_buy"]                       # at least one seat recommended
    assert d["n_on_api"] == 1                      # the light user stays on API
    assert "procurement_mix" in TOOLS


def test_procurement_mix_without_people_is_honest():
    d = _payload(handle(_req("tools/call", {"name": "procurement_mix", "arguments": {}}), REPORT))
    assert "no per-person spend" in d["recommendation"]


def test_unknown_tool_errors():
    resp = _call("teleport")
    assert resp["error"]["code"] == -32602


# --------------------------- default data ---------------------------------- #
def test_load_report_default_is_demoable():
    rep = load_report()
    assert rep.get("spend", {}).get("total_usd", 0) > 0
    # The server can answer over the bundled demo out of the box.
    d = _payload(handle(_req("tools/call", {"name": "spend_overview"}), rep))
    assert d["total_usd"] > 0
