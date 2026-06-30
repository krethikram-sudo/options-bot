"""Procurement-mix optimization — seat plans vs. API credits (advisory, read-only).

The fourth procurement mode alongside `commitment.py`'s on-demand / committed-spend
/ provisioned throughput. Compute spend is wildly uneven across employees — a few
engineers dominate, most staff are light — so buying a flat-fee seat (enterprise /
subscription) plan for *everyone* wastes money on light users, while buying API
credits for everyone pays a per-token premium on the heavy users. Given Outlay's
per-employee attributed spend, there's a cheaper **mix**: seats for the heavy users,
API for the rest. This module finds it.

Everything is normalized to **API-equivalent dollars** — what each person's tokens
would cost at API list rates, which is exactly what the attribution pipeline already
computes. For person *i* with monthly API-equivalent usage `uᵢ` and a seat plan *p*
with flat fee `f_p` and included capacity `c_p` (the API-$ a seat covers before usage
spills back to API):

    cost_on_api(i)     = uᵢ
    cost_on_plan(i, p) = f_p + max(0, uᵢ − c_p)      # flat fee + overflow at API rates

So a seat beats API exactly when `uᵢ > f_p`, and the per-person saving is
`min(uᵢ, c_p) − f_p` (maxing out once the seat saturates at `c_p`). The optimizer
assigns each person to the cheapest mode, honoring plan min-seat counts and any
platform fee, and reports the optimal seat counts, the total vs. the status quo, and
a sensitivity band on the (estimated) seat capacity.

Advisory and metadata-only: inputs are per-person dollar figures, never prompts; we
recommend, the customer buys the seats with the vendor. Seat fees and capacities are
configurable estimates — we never claim to see usage *inside* a subscription.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

_EPS = 1e-9


# --------------------------------------------------------------------------- #
# Plan catalog (the configurable rate card for seat/subscription plans)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PlanOption:
    """One seat/subscription plan, in API-equivalent dollars.

    `fee_usd` is the flat $/seat/month. `capacity_usd` is the API-equivalent value of
    usage a seat covers before usage spills back to API (an estimate the customer
    tunes — a subscription's real limit is rate-based, not a clean dollar figure).
    `min_seats` and `platform_fee_usd` capture enterprise floors. Defaults are
    `illustrative` — directional until the customer enters their real terms.
    """

    name: str
    fee_usd: float                  # flat $/seat/month
    capacity_usd: float             # API-equivalent $/month one seat covers before overflow
    provider: str = ""
    min_seats: int = 0              # enterprise plans often require a seat floor
    platform_fee_usd: float = 0.0   # fixed monthly fee charged if the plan is used at all
    illustrative: bool = True

    @property
    def headroom_usd(self) -> float:
        """The most a single saturated seat can save vs. API (`c_p − f_p`)."""
        return max(0.0, self.capacity_usd - self.fee_usd)


# Illustrative starter catalog — directional values the customer replaces with their
# real plan terms. Capacities are API-equivalent estimates, not published numbers.
_DEFAULT_CATALOG = (
    PlanOption("Claude Pro", 20.0, 120.0, provider="anthropic"),
    PlanOption("Claude Team seat", 30.0, 180.0, provider="anthropic"),
    PlanOption("Claude Max 5×", 100.0, 600.0, provider="anthropic"),
    PlanOption("Claude Max 20×", 200.0, 1500.0, provider="anthropic"),
    PlanOption("Claude Enterprise seat", 60.0, 450.0, provider="anthropic", min_seats=70),
)


def default_catalog() -> list[PlanOption]:
    """A copy of the illustrative seat-plan catalog (customer-tunable)."""
    return list(_DEFAULT_CATALOG)


def _scaled_catalog(catalog: list[PlanOption], factor: float) -> list[PlanOption]:
    """Catalog with every seat capacity scaled by `factor` — for sensitivity bands."""
    return [PlanOption(p.name, p.fee_usd, max(0.0, p.capacity_usd * factor), p.provider,
                       p.min_seats, p.platform_fee_usd, p.illustrative) for p in catalog]


# --------------------------------------------------------------------------- #
# Per-person economics
# --------------------------------------------------------------------------- #
def _plan_cost(usage_usd: float, plan: PlanOption) -> float:
    """Cost of serving `usage_usd` (API-equivalent) on one seat of `plan`."""
    return plan.fee_usd + max(0.0, usage_usd - plan.capacity_usd)


def _best_mode(usage_usd: float, catalog: list[PlanOption]):
    """Cheapest mode for one person, ignoring plan-level overhead.

    Returns (mode, plan_or_None, cost_usd, saturated). `mode` is "api" or the plan
    name; `saturated` means usage meets/exceeds the seat's capacity (overflowing).
    """
    best_cost = usage_usd          # API baseline
    best_plan: Optional[PlanOption] = None
    for p in catalog:
        c = _plan_cost(usage_usd, p)
        if c < best_cost - _EPS:
            best_cost, best_plan = c, p
    if best_plan is None:
        return "api", None, usage_usd, False
    return best_plan.name, best_plan, best_cost, usage_usd >= best_plan.capacity_usd


@dataclass
class PersonPlan:
    """The recommended procurement mode for one person."""

    user: str
    usage_usd: float          # monthly API-equivalent spend (what we measure)
    mode: str                 # "api" | plan name
    plan_name: Optional[str]
    cost_usd: float           # cost under the recommended mode
    api_cost_usd: float       # cost if left on API (== usage_usd)
    savings_usd: float        # api_cost_usd − cost_usd
    saturated: bool           # seat maxed, overflow billed at API


@dataclass
class MixResult:
    """The optimal seat/API mix across the workforce."""

    people: list[PersonPlan]
    seats_by_plan: dict                 # plan name -> seat count to buy
    status_quo_usd: float               # everyone on API — the honest common baseline
    optimized_usd: float                # optimal mix, incl. plan overhead
    total_savings_usd: float
    savings_rate: float                 # total_savings / status_quo
    n_on_plan: int
    n_on_api: int
    savings_low_usd: float              # sensitivity: seat capacity −band
    savings_high_usd: float             # sensitivity: seat capacity +band
    capacity_sensitivity: float         # the ± fraction applied
    unattributed_usd: float = 0.0       # spend with no resolved person — stays on API
    note: str = ""
    breakevens: dict = field(default_factory=dict)   # plan name -> usage where seat beats API


def _assign(pees: list[tuple[str, float]], catalog: list[PlanOption]):
    """Assign each (user, usage) to its cheapest mode, then prune plans whose realized
    savings don't cover their overhead (platform fee + empty min-seat padding).

    Returns (chosen, kept_plans) where chosen maps user -> (mode, plan, cost, saturated).
    """
    available = list(catalog)
    while True:
        chosen = {u: _best_mode(usage, available) for u, usage in pees}
        usage_by_user = {u: usage for u, usage in pees}
        groups: dict[str, list] = defaultdict(list)
        for u, (mode, plan, cost, _sat) in chosen.items():
            if plan is not None:
                groups[plan.name].append((u, cost))
        drop = None
        for p in available:
            assignees = groups.get(p.name, [])
            n = len(assignees)
            if n == 0:
                continue
            realized = sum(usage_by_user[u] - cost for u, cost in assignees)   # savings vs API
            empty_seats = max(0, p.min_seats - n)
            overhead = p.platform_fee_usd + empty_seats * p.fee_usd
            if realized <= overhead + _EPS:        # plan not worth its floor → drop it
                drop = p
                break
        if drop is None:
            return chosen, available
        available = [p for p in available if p.name != drop.name]


def optimize_mix(people: list[dict], catalog: Optional[list[PlanOption]] = None, *,
                 capacity_sensitivity: float = 0.3) -> MixResult:
    """Find the cheapest seat/API mix from per-person monthly API-equivalent spend.

    `people` is a list of dicts with a `user` and a monthly usage figure under
    `usage_usd` (or `spent_usd`). `(unattributed)` spend can't be put on a seat, so it
    is reported separately and left on API. `capacity_sensitivity` sets the ± band on
    seat capacity for the savings range.
    """
    catalog = catalog if catalog is not None else default_catalog()

    pees: list[tuple[str, float]] = []
    unattributed = 0.0
    for p in people or []:
        user = p.get("user")
        usage = max(0.0, float(p.get("usage_usd", p.get("spent_usd", 0.0)) or 0.0))
        if not user or user == "(unattributed)":
            unattributed += usage
            continue
        pees.append((user, usage))

    chosen, kept = _assign(pees, catalog)
    kept_names = {p.name for p in kept}
    plan_by_name = {p.name: p for p in kept}

    rows: list[PersonPlan] = []
    seats: dict[str, int] = defaultdict(int)
    n_plan = n_api = 0
    occupied_cost = 0.0
    for u, usage in pees:
        mode, plan, cost, sat = chosen[u]
        if plan is None or plan.name not in kept_names:
            mode, plan, cost, sat = "api", None, usage, False
        if plan is None:
            n_api += 1
        else:
            n_plan += 1
            seats[plan.name] += 1
        occupied_cost += cost
        rows.append(PersonPlan(user=u, usage_usd=round(usage, 2), mode=mode,
                               plan_name=(plan.name if plan else None),
                               cost_usd=round(cost, 2), api_cost_usd=round(usage, 2),
                               savings_usd=round(usage - cost, 2), saturated=sat))

    # Plan overhead for kept-and-used plans: platform fee + padding empty seats up to
    # the min-seat floor (seats you must buy even if no one fills them).
    overhead = 0.0
    final_seats: dict[str, int] = {}
    for name, n in seats.items():
        p = plan_by_name[name]
        billed_seats = max(n, p.min_seats)
        final_seats[name] = billed_seats
        overhead += p.platform_fee_usd + (billed_seats - n) * p.fee_usd

    status_quo = sum(usage for _, usage in pees)
    optimized = occupied_cost + overhead
    total_savings = status_quo - optimized

    rows.sort(key=lambda r: r.savings_usd, reverse=True)

    def _savings_at(factor: float) -> float:
        sc = _scaled_catalog(catalog, factor)
        ch, kp = _assign(pees, sc)
        kn = {p.name for p in kp}
        pbn = {p.name: p for p in kp}
        occ = 0.0
        used: dict[str, int] = defaultdict(int)
        for u, usage in pees:
            mode, plan, cost, _s = ch[u]
            if plan is None or plan.name not in kn:
                occ += usage
            else:
                occ += cost
                used[plan.name] += 1
        ov = 0.0
        for name, n in used.items():
            p = pbn[name]
            ov += p.platform_fee_usd + (max(n, p.min_seats) - n) * p.fee_usd
        return status_quo - (occ + ov)

    s = max(0.0, min(0.9, capacity_sensitivity))
    savings_low = _savings_at(1.0 - s) if s else total_savings
    savings_high = _savings_at(1.0 + s) if s else total_savings

    breakevens = {p.name: round(p.fee_usd, 2) for p in catalog}

    note = ("Illustrative seat fees/capacities — replace with your real plan terms. "
            "Advisory and metadata-only: we recommend the mix; you buy seats with the vendor.")

    return MixResult(
        people=rows,
        seats_by_plan=dict(sorted(final_seats.items(), key=lambda kv: -seats[kv[0]])),
        status_quo_usd=round(status_quo, 2),
        optimized_usd=round(optimized, 2),
        total_savings_usd=round(total_savings, 2),
        savings_rate=round(total_savings / status_quo, 4) if status_quo > 0 else 0.0,
        n_on_plan=n_plan,
        n_on_api=n_api,
        savings_low_usd=round(min(savings_low, savings_high), 2),
        savings_high_usd=round(max(savings_low, savings_high), 2),
        capacity_sensitivity=s,
        unattributed_usd=round(unattributed, 2),
        note=note,
        breakevens=breakevens,
    )


def format_planmix(result: MixResult, *, top: int = 8) -> str:
    """A compact text rendering of the mix recommendation (CLI / MCP / digests)."""
    if not result.people and result.unattributed_usd <= 0:
        return "Procurement mix: no per-person spend to optimize yet."
    lines = ["Procurement mix — seat plans vs. API (advisory)"]
    lines.append(
        f"  Status quo (all API): ${result.status_quo_usd:,.0f}/mo  →  "
        f"optimized: ${result.optimized_usd:,.0f}/mo  ·  "
        f"save ${result.total_savings_usd:,.0f}/mo ({result.savings_rate:.0%})")
    if result.seats_by_plan:
        seatbits = ", ".join(f"{n}× {name}" for name, n in result.seats_by_plan.items())
        lines.append(f"  Buy: {seatbits}  ·  keep {result.n_on_api} on API")
    else:
        lines.append(f"  Keep all {result.n_on_api} on API — no seat plan beats it at current usage.")
    if result.capacity_sensitivity:
        lines.append(
            f"  If seat capacity is ±{result.capacity_sensitivity:.0%}: "
            f"save ${result.savings_low_usd:,.0f}–${result.savings_high_usd:,.0f}/mo.")
    movers = [r for r in result.people if r.plan_name][:top]
    for r in movers:
        sat = " (saturated → overflow on API)" if r.saturated else ""
        lines.append(
            f"    {r.user}: ${r.usage_usd:,.0f}/mo on API → {r.plan_name} "
            f"${r.cost_usd:,.0f}/mo, save ${r.savings_usd:,.0f}{sat}")
    if result.unattributed_usd > 0:
        lines.append(
            f"  ${result.unattributed_usd:,.0f}/mo unattributed to a person — stays on API "
            "(improve coverage to optimize it).")
    lines.append("  " + result.note)
    return "\n".join(lines)
