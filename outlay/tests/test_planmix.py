"""Tests for the procurement-mix optimizer (outlay/planmix.py).

Pins the cost model (API vs seat), the per-person breakeven, seat saturation /
overflow, min-seat pruning of enterprise plans, the sensitivity band, unattributed
handling, and that the optimizer never costs more than all-API."""

from outlay.planmix import (
    MixResult,
    PlanOption,
    default_catalog,
    format_planmix,
    optimize_mix,
    _best_mode,
    _plan_cost,
)


# A tiny, deterministic catalog so the math is checkable by hand.
TEAM = PlanOption("Team", fee_usd=30.0, capacity_usd=180.0, provider="anthropic")
MAX = PlanOption("Max", fee_usd=200.0, capacity_usd=1500.0, provider="anthropic")
CATALOG = [TEAM, MAX]


def _people(*pairs):
    return [{"user": u, "usage_usd": v} for u, v in pairs]


# --- per-person cost model ----------------------------------------------------

def test_plan_cost_below_capacity_is_flat_fee():
    assert _plan_cost(100.0, TEAM) == 30.0          # under capacity → just the seat fee


def test_plan_cost_above_capacity_adds_overflow_at_api():
    # 250 of usage, seat covers 180 → 30 fee + 70 overflow = 100
    assert _plan_cost(250.0, TEAM) == 100.0


def test_best_mode_light_user_stays_on_api():
    mode, plan, cost, sat = _best_mode(8.0, CATALOG)   # below the $30 fee
    assert mode == "api" and plan is None and cost == 8.0 and not sat


def test_best_mode_heavy_user_takes_a_seat():
    mode, plan, cost, sat = _best_mode(160.0, CATALOG)  # > fee, < capacity
    assert plan is TEAM and cost == 30.0 and not sat


def test_best_mode_saturated_user_overflows():
    mode, plan, cost, sat = _best_mode(300.0, CATALOG)  # > Team capacity
    assert plan is TEAM and cost == 30.0 + 120.0 and sat


def test_breakeven_is_the_seat_fee():
    # at exactly the fee, API and seat tie → we keep API (no strict improvement)
    assert _best_mode(30.0, CATALOG)[0] == "api"
    # a dollar over the fee, the seat wins
    assert _best_mode(31.0, CATALOG)[1] is TEAM


# --- whole-org optimization ---------------------------------------------------

def test_mixed_org_assigns_each_person_to_cheapest_mode():
    # one heavy engineer, one HR light user
    res = optimize_mix(_people(("eng", 600.0), ("hr", 10.0)), CATALOG, capacity_sensitivity=0)
    by_user = {r.user: r for r in res.people}
    assert by_user["eng"].plan_name == "Max"           # 600 < 1500 cap → $200 flat
    assert by_user["eng"].cost_usd == 200.0
    assert by_user["hr"].mode == "api" and by_user["hr"].cost_usd == 10.0
    # status quo 610, optimized 210 → save 400
    assert res.status_quo_usd == 610.0
    assert res.optimized_usd == 210.0
    assert res.total_savings_usd == 400.0
    assert res.n_on_plan == 1 and res.n_on_api == 1
    assert res.seats_by_plan == {"Max": 1}


def test_optimizer_never_worse_than_all_api():
    res = optimize_mix(_people(("a", 5.0), ("b", 12.0), ("c", 25.0)), CATALOG)
    # nobody clears the $30 fee → everyone on API, zero savings, never negative
    assert res.total_savings_usd == 0.0
    assert res.optimized_usd == res.status_quo_usd
    assert res.seats_by_plan == {}
    assert res.n_on_api == 3


def test_each_person_gets_their_best_plan_tier():
    res = optimize_mix(_people(("light_pro", 150.0), ("whale", 5000.0)), CATALOG,
                       capacity_sensitivity=0)
    by_user = {r.user: r for r in res.people}
    assert by_user["light_pro"].plan_name == "Team"        # 150 → Team $30 beats Max $200
    assert by_user["whale"].plan_name == "Max"             # huge usage → Max, saturated
    assert by_user["whale"].saturated is True


# --- enterprise min-seat pruning ---------------------------------------------

def test_min_seat_floor_prunes_a_plan_that_cannot_pay_for_itself():
    # Enterprise seat is cheaper per heavy user but needs 70 seats; with only 2 users
    # the 68 empty seats make it a loss → optimizer must NOT pick it.
    ent = PlanOption("Enterprise", fee_usd=40.0, capacity_usd=400.0, min_seats=70)
    res = optimize_mix(_people(("e1", 300.0), ("e2", 350.0)), [TEAM, ent],
                       capacity_sensitivity=0)
    assert "Enterprise" not in res.seats_by_plan          # pruned by the seat floor
    assert res.seats_by_plan == {"Team": 2}               # falls back to Team
    assert res.total_savings_usd > 0


def test_min_seat_plan_used_when_enough_heavy_users():
    ent = PlanOption("Enterprise", fee_usd=40.0, capacity_usd=400.0, min_seats=3)
    res = optimize_mix(_people(("a", 390.0), ("b", 390.0), ("c", 390.0), ("d", 390.0)),
                       [ent], capacity_sensitivity=0)
    # 4 heavy users, floor of 3 met → plan is worth it
    assert res.seats_by_plan == {"Enterprise": 4}
    assert res.total_savings_usd > 0


# --- sensitivity, unattributed, formatting -----------------------------------

def test_capacity_sensitivity_band_brackets_savings():
    res = optimize_mix(_people(("eng", 600.0)), CATALOG, capacity_sensitivity=0.3)
    assert res.savings_low_usd <= res.total_savings_usd <= res.savings_high_usd


def test_unattributed_spend_is_reported_not_optimized():
    res = optimize_mix(_people(("eng", 600.0), ("(unattributed)", 90.0)), CATALOG,
                       capacity_sensitivity=0)
    assert res.unattributed_usd == 90.0
    assert all(r.user != "(unattributed)" for r in res.people)
    # status quo counts only attributed spend (what a seat could cover)
    assert res.status_quo_usd == 600.0


def test_default_catalog_is_illustrative_and_nonempty():
    cat = default_catalog()
    assert cat and all(p.illustrative for p in cat)
    assert all(p.capacity_usd > p.fee_usd for p in cat)   # every default plan has headroom


def test_format_planmix_renders_recommendation():
    res = optimize_mix(_people(("eng", 600.0), ("hr", 10.0)), CATALOG)
    out = format_planmix(res)
    assert "Procurement mix" in out
    assert "Max" in out and "save" in out.lower()
    assert "eng" in out


def test_empty_input_is_handled():
    res = optimize_mix([], CATALOG)
    assert isinstance(res, MixResult)
    assert res.total_savings_usd == 0.0
    assert "no per-person spend" in format_planmix(res)


def test_cli_planmix_flag_appends_recommendation():
    from outlay import cli
    out = cli.run(cli._FIXTURES / "anthropic_usage.json",
                  cli._FIXTURES / "github_issues.json", 30, planmix=True)
    assert "Procurement mix" in out


def test_serialize_includes_people_rollup():
    # The JSON report (machine API / MCP) carries per-person spend, biggest first.
    from outlay import cli
    import json as _json
    rep = _json.loads(cli.run(cli._FIXTURES / "anthropic_usage.json",
                              cli._FIXTURES / "github_issues.json", 30, as_json=True))
    assert "people" in rep and isinstance(rep["people"], list)
    if len(rep["people"]) >= 2:
        assert rep["people"][0]["spent_usd"] >= rep["people"][1]["spent_usd"]
