"""Tests for the cost-fidelity proof (cache-aware vs naive token-count costing)."""

from datetime import datetime

from outlay.models import UsageEvent
from outlay.pricing import rate_for
from outlay.proof import cost_fidelity, format_cost_fidelity


def _ev(model="claude-opus-4-8", inp=0, out=0, cr=0, cw=0, _id="e"):
    return UsageEvent(id=_id, provider="anthropic", model=model, ts=datetime(2026, 6, 20),
                      input_tokens=inp, output_tokens=out, cache_read_tokens=cr, cache_write_tokens=cw)


def test_cache_heavy_workload_inflates_under_naive_costing():
    # A re-sent cached prefix every turn: cache reads dominate the token count.
    events = [_ev(inp=1_000, out=1_000, cr=1_000_000, cw=0, _id=f"e{i}") for i in range(5)]
    cf = cost_fidelity(events)
    r = rate_for("claude-opus-4-8")

    # Outlay prices cache reads at 0.1x; naive prices them at base input — so the
    # naive number is many times larger and that gap is almost entirely cache reads.
    assert cf.naive_usd > cf.outlay_usd * 3
    assert cf.inflation_factor == round(cf.naive_usd / cf.outlay_usd, 10) or cf.inflation_factor > 3
    assert cf.cache_read_share > 0.99
    assert cf.overstatement_usd == round(cf.naive_usd - cf.outlay_usd, 10) or cf.overstatement_usd > 0
    # the math: naive cache cost uses base input rate, Outlay uses 0.1x of it
    assert r.cache_read_mult == 0.1


def test_no_cache_means_no_inflation():
    # Pure uncached input + output: naive and cache-aware costs are identical.
    events = [_ev(inp=10_000, out=5_000, cr=0, cw=0)]
    cf = cost_fidelity(events)
    assert abs(cf.naive_usd - cf.outlay_usd) < 1e-9
    assert round(cf.inflation_factor, 3) == 1.0
    assert cf.cache_read_share == 0.0


def test_by_model_breakdown_and_dict_shape():
    events = [_ev(model="claude-opus-4-8", inp=100, out=100, cr=500_000),
              _ev(model="claude-haiku-4-5", inp=100, out=100, cr=500_000, _id="h")]
    cf = cost_fidelity(events)
    assert cf.events == 2
    d = cf.as_dict()
    assert set(d) >= {"events", "outlay_usd", "naive_usd", "overstatement_usd",
                      "inflation_factor", "cache_read_share", "tokens", "by_model"}
    assert set(d["by_model"]) == {"claude-opus-4-8", "claude-haiku-4-5"}
    # ordered by Outlay spend (opus is pricier) → opus first
    assert list(d["by_model"]) [0] == "claude-opus-4-8"
    assert d["tokens"]["cache_read"] == 1_000_000


def test_empty_is_safe():
    cf = cost_fidelity([])
    assert cf.events == 0 and cf.inflation_factor == 0.0 and cf.cache_read_share == 0.0
    assert "no usage events" in format_cost_fidelity(cf)


def test_format_is_readable():
    events = [_ev(inp=1_000, out=1_000, cr=1_000_000)]
    out = format_cost_fidelity(cost_fidelity(events))
    assert "COST FIDELITY" in out and "Inflation" in out and "Cache-read share" in out
