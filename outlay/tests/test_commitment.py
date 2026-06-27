"""Commitment & procurement optimization engine — decomposition, committed-spend
sizing, provisioned break-even, and pacing."""

import pytest

from outlay.commitment import (
    BreakEven,
    CommitmentTier,
    ProvisionedUnit,
    RateCard,
    break_even,
    decompose,
    pace_commitment,
    recommend_commitment,
)

# A representative Anthropic-style rate card: blended $9/Mtok on-demand, two
# committed-spend tiers, and a provisioned unit.
CARD = RateCard(
    provider="anthropic",
    on_demand_usd_per_mtok=9.0,
    tiers=(
        CommitmentTier(threshold_usd=10_000, discount=0.15),
        CommitmentTier(threshold_usd=50_000, discount=0.30),
    ),
    provisioned=ProvisionedUnit(unit="PTU", usd_per_hour=2.0, tokens_per_sec=50.0),
)


# --------------------------- rate card ------------------------------------- #
def test_discount_tiers_pick_best_applicable():
    assert CARD.discount_at(5_000) == 0.0
    assert CARD.discount_at(10_000) == 0.15
    assert CARD.discount_at(49_999) == 0.15
    assert CARD.discount_at(80_000) == 0.30


def test_invalid_discount_rejected():
    with pytest.raises(ValueError):
        CommitmentTier(threshold_usd=1, discount=1.0)


# --------------------------- decomposition --------------------------------- #
def test_decompose_flat_series_is_steady():
    p = decompose([100.0] * 30)
    assert p.floor_usd == pytest.approx(100.0)
    assert p.peak_usd == pytest.approx(100.0)
    assert p.cov == pytest.approx(0.0)
    assert p.steadiness == pytest.approx(1.0)
    assert p.spike_usd == pytest.approx(0.0)


def test_decompose_spiky_series_low_steadiness():
    # Mostly small with occasional big spikes → high CoV, low steadiness, floor << peak.
    series = [10.0] * 20 + [200.0] * 5
    p = decompose(series)
    assert p.floor_usd <= p.median_usd < p.peak_usd
    assert p.peak_usd == 200.0
    assert p.cov > 0.5
    assert p.steadiness < 0.5


def test_decompose_empty_is_zero():
    p = decompose([])
    assert p.floor_usd == 0.0 and p.n_periods == 0


def test_decompose_clamps_negative_spend():
    p = decompose([-5.0, 10.0, 10.0])
    assert p.floor_usd >= 0.0


# --------------------------- committed-spend sizing ------------------------ #
def test_recommend_commitment_orders_and_saves():
    # Daily floor ~ $1k → monthly floor ~ $30k; forecast monthly $40k on-demand.
    profile = decompose([1_000.0] * 30)
    scen = recommend_commitment(profile, forecast_usd=40_000.0, ratecard=CARD,
                                floor_periods=30, safety_buffer=0.10)
    labels = [s.label for s in scen]
    assert labels == ["conservative", "base", "aggressive"]
    # Commit rises conservative → aggressive.
    assert scen[0].commit_usd <= scen[1].commit_usd <= scen[2].commit_usd
    # Each scenario should net positive savings vs on-demand here.
    for s in scen:
        assert s.net_savings_usd > 0
        assert 0.0 <= s.effective_savings_rate <= 0.30


def test_conservative_never_forfeits_when_floor_solid():
    profile = decompose([1_000.0] * 30)
    scen = recommend_commitment(profile, forecast_usd=40_000.0, ratecard=CARD, floor_periods=30)
    conservative = scen[0]
    assert conservative.forfeited_usd == 0.0
    assert conservative.forfeit_risk == "none"


def test_overcommit_forfeits_and_is_flagged():
    # Tiny actual usage but we model a big commit by hand via the economics path:
    # forecast far below commit floor → billed == commit, big forfeit.
    profile = decompose([5_000.0] * 30)          # $150k/mo floor
    scen = recommend_commitment(profile, forecast_usd=20_000.0, ratecard=CARD, floor_periods=30)
    base = scen[1]
    assert base.forfeited_usd > 0
    assert base.forfeit_risk in ("low", "elevated")
    # Billed at least the commit; net savings can be negative when over-committed.
    assert base.billed_usd >= base.commit_usd - 0.01


# --------------------------- provisioned break-even ------------------------ #
def test_break_even_formula():
    be = break_even(CARD)
    # U* = (2.0/hr) / (9e-6 $/tok * 50 tok/s * 3600) = 2.0 / 1.62 = ~1.2346
    assert be.util_threshold == pytest.approx(2.0 / (9e-6 * 50 * 3600), rel=1e-4)
    assert isinstance(be, BreakEven)


def test_break_even_recommends_when_floor_exceeds_threshold():
    # Cheap provisioned unit so U* < 1, then a steady floor above it.
    card = RateCard("anthropic", on_demand_usd_per_mtok=30.0,
                    provisioned=ProvisionedUnit("PTU", usd_per_hour=2.0, tokens_per_sec=50.0))
    be = break_even(card, steady_tokens_per_sec=40.0)
    assert be.util_threshold < 1.0
    assert be.steady_utilization == pytest.approx(40.0 / 50.0)
    assert be.recommend_provisioned is True


def test_break_even_holds_when_floor_too_low():
    card = RateCard("anthropic", on_demand_usd_per_mtok=30.0,
                    provisioned=ProvisionedUnit("PTU", usd_per_hour=2.0, tokens_per_sec=50.0))
    be = break_even(card, steady_tokens_per_sec=1.0)
    assert be.recommend_provisioned is False


def test_break_even_requires_provisioned_unit():
    with pytest.raises(ValueError):
        break_even(RateCard("anthropic", on_demand_usd_per_mtok=9.0))


# --------------------------- pacing ---------------------------------------- #
def test_pace_on_track():
    p = pace_commitment(commit_usd=120_000, used_to_date_usd=60_000, elapsed_fraction=0.5)
    assert p.status == "on_track"
    assert p.utilization_at_end == pytest.approx(1.0, abs=0.02)


def test_pace_forfeit_risk_under_pace():
    # Halfway through, only used 30% of commit → projects to 60% → forfeit.
    p = pace_commitment(commit_usd=100_000, used_to_date_usd=30_000, elapsed_fraction=0.5)
    assert p.status == "forfeit_risk"
    assert p.projected_forfeit_usd > 0
    assert "forfeit" in p.message.lower()


def test_pace_overage_risk_over_pace():
    # Halfway, already used 80% → projects to 160% → overage.
    p = pace_commitment(commit_usd=100_000, used_to_date_usd=80_000, elapsed_fraction=0.5)
    assert p.status == "overage_risk"
    assert p.projected_overage_usd > 0


def test_pace_uses_forecast_remaining_when_given():
    # Linear would project forfeit, but the forecast says a big H2 ramp → on track.
    p = pace_commitment(commit_usd=100_000, used_to_date_usd=30_000, elapsed_fraction=0.5,
                        forecast_remaining_usd=68_000)
    assert p.projected_end_usd == pytest.approx(98_000)
    assert p.status == "on_track"
