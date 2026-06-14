"""Prompt-level savings audit (feature D)."""

from modelpilot.promptsavings import (
    audit,
    caching_opportunity,
    context_bloat,
    headline,
)


def _row(session, inp, out, cache_read=0, model="claude-fable-5", rid="x"):
    return {"id": rid, "ts": 0.0, "session_key": session, "original_model": model,
            "input_tokens": inp, "output_tokens": out,
            "cache_read_tokens": cache_read, "cache_write_tokens": 0}


def test_caching_opportunity_flags_uncached_multiturn():
    # 4-turn session, growing prefix, caching OFF -> savings on the repeated floor.
    rows = [_row("s1", 5000, 200), _row("s1", 6000, 200),
            _row("s1", 7000, 200), _row("s1", 8000, 200)]
    r = caching_opportunity(rows)
    assert r["n_sessions"] == 1
    # stable prefix 5000, 3 repeats, fable input $10/Mtok, 90% of it saved
    expected = 5000 * 3 * (10.0 / 1_000_000) * 0.9
    assert abs(r["total_saved"] - expected) < 1e-9


def test_caching_opportunity_ignores_already_cached():
    rows = [_row("s1", 5000, 200, cache_read=4000), _row("s1", 6000, 200, cache_read=5000)]
    assert caching_opportunity(rows)["total_saved"] == 0.0


def test_caching_opportunity_ignores_single_turn():
    assert caching_opportunity([_row("s1", 9000, 200)])["total_saved"] == 0.0


def test_context_bloat_flags_large_input_small_output():
    rows = [_row("s1", 40000, 100, rid="big")]  # ratio 400, well over threshold
    r = context_bloat(rows)
    assert r["n_requests"] == 1
    expected = 40000 * 0.30 * (10.0 / 1_000_000)
    assert abs(r["total_saved"] - expected) < 1e-9


def test_context_bloat_ignores_proportionate_requests():
    assert context_bloat([_row("s1", 4000, 1000)])["total_saved"] == 0.0


def test_audit_projects_monthly_and_headline():
    rows = [_row("s1", 5000, 200), _row("s1", 6000, 200), _row("s1", 7000, 200)]
    rep = audit(rows, window_days=10.0)
    assert rep["total_saved"] > 0
    assert rep["projected_monthly"] == rep["total_saved"] / 10.0 * 30
    assert "prompt caching" in headline(rep)


def test_audit_does_not_double_count_caching_and_bloat():
    # A caching session whose turns ALSO look bloated must be credited once
    # (to caching), not in both buckets.
    rows = [_row("s1", 9000, 100), _row("s1", 9000, 100), _row("s1", 9000, 100)]
    rep = audit(rows, window_days=7.0)
    assert rep["caching"]["total_saved"] > 0
    assert rep["bloat"]["total_saved"] == 0.0  # excluded — already credited to caching


def test_headline_none_when_nothing_material():
    assert headline(audit([_row("s1", 100, 100)], window_days=7.0)) is None
