"""Commitment & procurement optimization — advisory, read-only.

Specced in `docs/spec-commitment-optimization.md`. This is the engine behind the
highest-$ incremental lever (market analysis §10, product strategy §3B): from a
customer's *attributed and forecasted* AI usage, recommend the cheapest **way to
pay** for compute — on-demand vs committed-spend discount vs provisioned
throughput — and pace any commitments already in flight.

The whole module is **advisory**: it recommends; the customer executes the
commitment with the vendor. We never sit in the request path, and every input is
a number (metadata), never a contract document — same posture as the rest of
Outlay.

Three outputs, matching the spec:
  1. `recommend_commitment` — committed-spend discount sizing at three risk levels.
  2. `break_even`           — provisioned-throughput utilization break-even (U*).
  3. `pace_commitment`      — forfeit/overage projection for an active commitment.

All money is per-period (default monthly) and all logic is pure — no I/O, no
provider calls — so it back-tests and unit-tests cleanly.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

# Reuse the forecast module's percentile so the "floor" here lines up exactly
# with the p10..p90 framing used everywhere else in the product.
from .forecast import _percentile

if TYPE_CHECKING:
    from .models import UsageEvent


# --------------------------------------------------------------------------- #
# Rate-card config (the "New" entities in the spec's data model)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CommitmentTier:
    """One committed-spend discount tier: commit ≥ `threshold_usd`/period → `discount`."""

    threshold_usd: float
    discount: float          # fraction off on-demand, e.g. 0.20 == 20% off

    def __post_init__(self) -> None:
        if not 0.0 <= self.discount < 1.0:
            raise ValueError(f"discount must be in [0, 1): {self.discount}")


@dataclass(frozen=True)
class ProvisionedUnit:
    """A dedicated-capacity unit (Azure OpenAI PTU, Bedrock provisioned, reserved GPU).

    PTU pricing is frequently negotiated, so callers should pass the customer's
    actual quote rather than a list price.
    """

    unit: str                # "PTU" | "GPU" | ...
    usd_per_hour: float      # price of one unit for one hour
    tokens_per_sec: float    # sustained throughput capacity of one unit


@dataclass(frozen=True)
class RateCard:
    """Per-provider procurement options. Tiers are stored sorted ascending."""

    provider: str
    on_demand_usd_per_mtok: float            # blended $/1M tokens at rack rate
    tiers: tuple[CommitmentTier, ...] = ()
    provisioned: Optional[ProvisionedUnit] = None

    def discount_at(self, commit_usd: float) -> float:
        """Best discount available when committing `commit_usd`/period (0 if below all tiers)."""
        best = 0.0
        for t in self.tiers:
            if commit_usd >= t.threshold_usd:
                best = max(best, t.discount)
        return best

    @property
    def on_demand_usd_per_token(self) -> float:
        return self.on_demand_usd_per_mtok / 1_000_000.0


# Illustrative committed-spend tiers. Vendor committed-use discounts are
# privately negotiated and not published, so these are clearly-labeled defaults a
# customer overrides with their own quote — never presented as the vendor's
# actual rate card.
_ILLUSTRATIVE_TIERS: tuple[CommitmentTier, ...] = (
    CommitmentTier(threshold_usd=10_000, discount=0.10),
    CommitmentTier(threshold_usd=50_000, discount=0.20),
    CommitmentTier(threshold_usd=250_000, discount=0.30),
)


def default_ratecard(provider: str = "anthropic",
                     on_demand_usd_per_mtok: float = 9.0) -> RateCard:
    """A starter rate card with *illustrative* commitment tiers (10/50/250k → 10/20/30%).

    `on_demand_usd_per_mtok` should be the customer's blended realized rate (we can
    compute it from their own attributed spend). Discounts are placeholders the
    customer replaces with their negotiated terms.
    """
    return RateCard(provider=provider,
                    on_demand_usd_per_mtok=on_demand_usd_per_mtok,
                    tiers=_ILLUSTRATIVE_TIERS)


def default_provisioned(unit: str = "PTU", usd_per_hour: float = 1.0,
                        tokens_per_sec: float = 50.0) -> ProvisionedUnit:
    """An *illustrative* provisioned-throughput unit for directional break-even math.

    Real PTU/reserved-GPU pricing and per-model throughput are negotiated and
    model-specific — the customer replaces these with their actual quote before
    treating the recommendation as anything but directional.
    """
    return ProvisionedUnit(unit=unit, usd_per_hour=usd_per_hour, tokens_per_sec=tokens_per_sec)


def daily_spend_series(events: "list[UsageEvent]") -> list[float]:
    """Collapse usage events into a per-calendar-day spend series (USD), date-sorted.

    The series `decompose()` consumes — built from the same cost model as the rest
    of the pipeline so the floor/spike split matches the attributed numbers.
    """
    from .pricing import cost_usd

    by_day: dict[str, float] = defaultdict(float)
    for e in events:
        by_day[e.ts.date().isoformat()] += cost_usd(e)
    return [by_day[d] for d in sorted(by_day)]


# --------------------------------------------------------------------------- #
# 1. Baseline-vs-spike decomposition (spec §3a)
# --------------------------------------------------------------------------- #
@dataclass
class SpendProfile:
    """Decomposition of a per-period spend series into a steady floor and spike."""

    floor_usd: float         # steady "always-on" floor (low-percentile of the series)
    median_usd: float
    peak_usd: float
    mean_usd: float
    cov: float               # coefficient of variation (std / mean)
    steadiness: float        # 1 - cov, clamped to [0, 1]; higher == better commit candidate
    n_periods: int

    @property
    def spike_usd(self) -> float:
        """The remainder above the floor at a typical (median) period."""
        return max(0.0, self.median_usd - self.floor_usd)


def decompose(series: list[float], floor_q: float = 0.20) -> SpendProfile:
    """Split a per-period spend series into its steady floor vs spiky remainder.

    `floor_q` is the percentile taken as the always-on floor (default p20 — the
    spec's p10–p25 range). Steadier series (low coefficient of variation) are
    better commit/provision candidates; that's surfaced as `steadiness`.
    """
    vals = [max(0.0, float(v)) for v in series]
    if not vals:
        return SpendProfile(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
    sv = sorted(vals)
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    std = var ** 0.5
    cov = (std / mean) if mean > 0 else 0.0
    return SpendProfile(
        floor_usd=_percentile(sv, floor_q),
        median_usd=_percentile(sv, 0.5),
        peak_usd=sv[-1],
        mean_usd=mean,
        cov=cov,
        steadiness=max(0.0, min(1.0, 1.0 - cov)),
        n_periods=n,
    )


# --------------------------------------------------------------------------- #
# 2. Committed-spend discount recommendation (spec §3b)
# --------------------------------------------------------------------------- #
@dataclass
class CommitScenario:
    """Modeled economics of committing `commit_usd`/period at the resulting tier.

    Cost model (documented so the number is auditable): the customer commits
    `commit_usd` of *discounted* spend per period and earns `discount` on all
    usage. With on-demand-equivalent usage `F` (what the same tokens cost at rack
    rate), the discounted cost of that usage is `F*(1-d)`. The customer is billed
    `max(commit_usd, F*(1-d))` — they forfeit the commit they don't consume.

        billed         = max(commit, F*(1-d))
        forfeited      = max(0, commit - F*(1-d))
        net_savings    = F - billed          # vs paying on-demand
    """

    label: str               # "conservative" | "base" | "aggressive"
    commit_usd: float
    discount: float
    on_demand_usd: float     # F — forecast usage at rack rate
    billed_usd: float
    forfeited_usd: float
    net_savings_usd: float
    effective_savings_rate: float    # net_savings / on_demand
    forfeit_risk: str        # "none" | "low" | "elevated"


def _commit_economics(label: str, commit_usd: float, on_demand_usd: float,
                      ratecard: RateCard) -> CommitScenario:
    d = ratecard.discount_at(commit_usd)
    discounted_usage = on_demand_usd * (1.0 - d)
    billed = max(commit_usd, discounted_usage)
    forfeited = max(0.0, commit_usd - discounted_usage)
    net = on_demand_usd - billed
    rate = (net / on_demand_usd) if on_demand_usd > 0 else 0.0
    if forfeited <= 0:
        risk = "none"
    elif forfeited <= 0.10 * billed:
        risk = "low"
    else:
        risk = "elevated"
    return CommitScenario(
        label=label,
        commit_usd=round(commit_usd, 2),
        discount=d,
        on_demand_usd=round(on_demand_usd, 2),
        billed_usd=round(billed, 2),
        forfeited_usd=round(forfeited, 2),
        net_savings_usd=round(net, 2),
        effective_savings_rate=round(rate, 4),
        forfeit_risk=risk,
    )


def recommend_commitment(
    profile: SpendProfile,
    forecast_usd: float,
    ratecard: RateCard,
    *,
    floor_periods: float = 1.0,
    safety_buffer: float = 0.10,
) -> list[CommitScenario]:
    """Size a committed-spend discount at three risk levels.

    The commit is anchored on the **steady floor** so utilization stays above the
    commitment and forfeit is rare:

      * conservative — floor × (1 − 2·buffer): almost never forfeits.
      * base         — floor × (1 − buffer): the recommended posture.
      * aggressive   — min(median, forecast)-anchored: captures more discount,
                       accepts some forfeit risk if usage dips.

    `forecast_usd` is the on-demand-equivalent spend over the commit period (from
    the forecast engine). `floor_periods` scales the per-period floor to the commit
    term (e.g. 30 for a daily series committed monthly). Returns scenarios sorted
    conservative → aggressive; `net_savings_usd` lets the caller pick.
    """
    floor_term = profile.floor_usd * floor_periods
    median_term = profile.median_usd * floor_periods
    b = max(0.0, min(0.5, safety_buffer))
    candidates = [
        ("conservative", floor_term * (1.0 - 2.0 * b)),
        ("base", floor_term * (1.0 - b)),
        ("aggressive", max(median_term, min(forecast_usd, median_term * 1.0)) * (1.0 - b)),
    ]
    return [_commit_economics(label, max(0.0, c), forecast_usd, ratecard)
            for label, c in candidates]


# --------------------------------------------------------------------------- #
# 3. Provisioned-throughput break-even (spec §3c)
# --------------------------------------------------------------------------- #
@dataclass
class BreakEven:
    """Provisioned-vs-on-demand break-even for one provisioned unit."""

    util_threshold: float        # U* — fraction of unit capacity above which provisioned wins
    breakeven_tokens_per_hour: float
    on_demand_cost_at_capacity_per_hour: float   # cost to buy a full unit-hour of throughput on-demand
    provisioned_cost_per_hour: float
    recommend_provisioned: bool  # given the supplied steady utilization
    steady_utilization: Optional[float] = None
    rationale: str = ""


def break_even(
    ratecard: RateCard,
    *,
    steady_tokens_per_sec: Optional[float] = None,
) -> BreakEven:
    """Compute the provisioned break-even utilization U* for `ratecard.provisioned`.

        U*  =  (provisioned $/hr)  /  (on_demand $/token × tokens_per_sec × 3600)

    Above U* of the unit's capacity, the dedicated lane is cheaper than paying
    on-demand for the same throughput. If `steady_tokens_per_sec` (the always-on
    floor throughput, from the attribution join) is given, we also say whether to
    move it to provisioned.
    """
    pu = ratecard.provisioned
    if pu is None:
        raise ValueError("rate card has no provisioned unit")
    capacity_per_hour = pu.tokens_per_sec * 3600.0
    on_demand_at_capacity = ratecard.on_demand_usd_per_token * capacity_per_hour
    u_star = (pu.usd_per_hour / on_demand_at_capacity) if on_demand_at_capacity > 0 else float("inf")
    u_star = max(0.0, u_star)
    steady_util = None
    recommend = False
    rationale = (
        f"Provisioned wins above {u_star:.0%} utilization of one {pu.unit} "
        f"({pu.tokens_per_sec:,.0f} tok/s capacity)."
    )
    if steady_tokens_per_sec is not None and pu.tokens_per_sec > 0:
        steady_util = steady_tokens_per_sec / pu.tokens_per_sec
        recommend = steady_util >= u_star
        if recommend:
            rationale += (
                f" Your steady floor runs at {steady_util:.0%} — move it to provisioned; "
                "keep spikes on-demand."
            )
        else:
            rationale += (
                f" Your steady floor is only {steady_util:.0%} — stay on-demand until it grows."
            )
    return BreakEven(
        util_threshold=round(u_star, 4),
        breakeven_tokens_per_hour=round(u_star * capacity_per_hour, 1),
        on_demand_cost_at_capacity_per_hour=round(on_demand_at_capacity, 4),
        provisioned_cost_per_hour=pu.usd_per_hour,
        recommend_provisioned=recommend,
        steady_utilization=round(steady_util, 4) if steady_util is not None else None,
        rationale=rationale,
    )


# --------------------------------------------------------------------------- #
# 4. Commitment pacing — forfeit / overage projection (spec §4)
# --------------------------------------------------------------------------- #
@dataclass
class CommitmentPace:
    """Where an active commitment lands at end-of-term, and the risk."""

    elapsed_fraction: float          # share of the term elapsed
    used_to_date_usd: float
    commit_usd: float
    expected_used_usd: float         # on-pace expectation at this point (linear)
    projected_end_usd: float         # extrapolated end-of-term consumption
    utilization_at_end: float        # projected_end / commit
    status: str                      # "on_track" | "forfeit_risk" | "overage_risk"
    projected_forfeit_usd: float
    projected_overage_usd: float
    message: str


def pace_commitment(
    commit_usd: float,
    used_to_date_usd: float,
    elapsed_fraction: float,
    *,
    forecast_remaining_usd: Optional[float] = None,
    forfeit_tolerance: float = 0.05,
) -> CommitmentPace:
    """Project end-of-term utilization of an active commitment and flag risk.

    Extends the shipped program-pacing rails. `elapsed_fraction` is how far through
    the term we are (0–1). End-of-term consumption is projected by linear run-rate,
    unless `forecast_remaining_usd` is supplied (forecast-projected remainder), in
    which case we use `used_to_date + forecast_remaining`.

    Status mirrors the budget rails: under-pace beyond `forfeit_tolerance` →
    `forfeit_risk` (amber/red); over-pace that exhausts the commit before term end
    → `overage_risk`.
    """
    ef = max(1e-6, min(1.0, elapsed_fraction))
    expected = commit_usd * ef
    if forecast_remaining_usd is not None:
        projected_end = used_to_date_usd + max(0.0, forecast_remaining_usd)
    else:
        projected_end = used_to_date_usd / ef          # linear run-rate
    util_end = (projected_end / commit_usd) if commit_usd > 0 else 0.0
    forfeit = max(0.0, commit_usd - projected_end)
    overage = max(0.0, projected_end - commit_usd)

    if util_end >= 1.0 + forfeit_tolerance:
        # Will exhaust the commit before term end → on-demand overage on the remainder.
        exhaust_at = (commit_usd / projected_end) if projected_end > 0 else 1.0
        status = "overage_risk"
        msg = (
            f"On pace to consume {util_end:.0%} of the ${commit_usd:,.0f} commit — "
            f"exhausted around {exhaust_at:.0%} through the term, then on-demand overage of "
            f"~${overage:,.0f}. Consider a higher tier."
        )
    elif util_end <= 1.0 - forfeit_tolerance:
        status = "forfeit_risk"
        msg = (
            f"On pace to use only {util_end:.0%} of the ${commit_usd:,.0f} commit — "
            f"~${forfeit:,.0f} forfeited. Shift workload onto it or renegotiate the tier."
        )
    else:
        status = "on_track"
        msg = f"On track — projected {util_end:.0%} utilization of the ${commit_usd:,.0f} commit."

    return CommitmentPace(
        elapsed_fraction=round(ef, 4),
        used_to_date_usd=round(used_to_date_usd, 2),
        commit_usd=round(commit_usd, 2),
        expected_used_usd=round(expected, 2),
        projected_end_usd=round(projected_end, 2),
        utilization_at_end=round(util_end, 4),
        status=status,
        projected_forfeit_usd=round(forfeit, 2),
        projected_overage_usd=round(overage, 2),
        message=msg,
    )


# --------------------------------------------------------------------------- #
# Text readout (CLI)
# --------------------------------------------------------------------------- #
def format_commitment(profile: SpendProfile, scenarios: list[CommitScenario],
                      ratecard: RateCard, *, period: str = "month") -> str:
    """Human-readable commitment recommendation block for the CLI report."""
    lines = [
        "Commitment & procurement optimization  (advisory — you execute with the vendor)",
        "=" * 78,
        f"  Spend profile  ({profile.n_periods} days):  "
        f"floor ${profile.floor_usd:,.0f}/day · median ${profile.median_usd:,.0f}/day · "
        f"peak ${profile.peak_usd:,.0f}/day",
        f"  Steadiness:  {profile.steadiness:.0%}  "
        f"(CoV {profile.cov:.2f}; higher steadiness ⇒ better commit candidate)",
        f"  On-demand rate:  ${ratecard.on_demand_usd_per_mtok:,.2f}/Mtok  "
        f"(illustrative tiers — replace with your negotiated terms)",
        "",
        f"  Committed-spend options (per {period}):",
        f"    {'scenario':<13}{'commit':>12}{'discount':>10}{'billed':>12}"
        f"{'net save':>11}{'eff rate':>10}  risk",
    ]
    for s in scenarios:
        lines.append(
            f"    {s.label:<13}{('$%s' % f'{s.commit_usd:,.0f}'):>12}"
            f"{('%.0f%%' % (s.discount * 100)):>10}"
            f"{('$%s' % f'{s.billed_usd:,.0f}'):>12}"
            f"{('$%s' % f'{s.net_savings_usd:,.0f}'):>11}"
            f"{s.effective_savings_rate:>10.1%}  {s.forfeit_risk}"
        )
    best = max(scenarios, key=lambda s: s.net_savings_usd) if scenarios else None
    if best:
        lines += [
            "",
            f"  ▶ Recommended: commit ${best.commit_usd:,.0f}/{period} ({best.label}) "
            f"→ ~${best.net_savings_usd:,.0f}/{period} net "
            f"({best.effective_savings_rate:.0%}), forfeit risk: {best.forfeit_risk}.",
        ]
    return "\n".join(lines)
