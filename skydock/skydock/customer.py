"""Customer-acquisition funnel (spec §9.3 sub-loop + §4.1-4.3).

Operates at a coarse daily tick rate while the operations layer runs at
seconds. The funnel tracks prospect arrivals, conversion to paid pilots,
per-pilot commitments, scenario allocation against those commitments,
cash balance, and runway.

When the funnel is enabled, scenario revenue is determined by allocation
to an active pilot's commitment (at that pilot's negotiated price)
rather than the flat config price. Scenarios delivered with no active
pilot demand are counted as "unsold inventory" — generated and stored
but not revenue-bearing.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


# Spec §4.1 named pilot prospects.
_PROSPECT_NAMES = [
    "Applied Intuition", "Foretellix", "Parallel Domain", "Cognata",
    "Aurora Sim", "Voyage Validation", "MoCap AV", "Mira Scenario",
    "Reka Drive", "Conway Labs",
]


@dataclass
class Pilot:
    pilot_id: str
    name: str
    signed_at_s: float
    scenarios_committed: int
    price_per_scenario: float
    scenarios_delivered: int = 0
    closed_at_s: Optional[float] = None

    @property
    def is_fulfilled(self) -> bool:
        return self.scenarios_delivered >= self.scenarios_committed

    @property
    def remaining(self) -> int:
        return max(0, self.scenarios_committed - self.scenarios_delivered)

    @property
    def revenue_to_date(self) -> float:
        return self.scenarios_delivered * self.price_per_scenario

    @property
    def commitment_value(self) -> float:
        return self.scenarios_committed * self.price_per_scenario


@dataclass
class Prospect:
    prospect_id: str
    name: str
    arrived_at_s: float
    expires_at_s: float
    quality_threshold_required: float    # min recent quality before they'll sign


@dataclass
class FunnelState:
    """Snapshot of funnel state for the dashboard panel."""
    prospects_active: int
    prospects_lifetime: int
    pilots_active: int
    pilots_fulfilled: int
    scenarios_committed: int
    scenarios_delivered_to_pilots: int
    scenarios_unsold: int
    revenue_usd: float
    cash_usd: float
    monthly_burn_usd: float
    monthly_revenue_rate_usd: float    # smoothed pilot rev / elapsed months
    runway_months: float               # cash / net burn (∞ if revenue ≥ burn)


class CustomerFunnel:
    """Monthly-scale customer pipeline that consumes operational deliveries.

    Daily tick: prospect arrivals, conversion decisions, burn-rate accrual.
    Per-delivery: allocate to the oldest unfulfilled pilot (FIFO).
    """

    def __init__(self, cfg, rng: random.Random):
        self.cfg = cfg
        self.rng = rng
        self.prospects: list[Prospect] = []
        self.pilots: list[Pilot] = []
        self.expired_prospects: int = 0
        self.scenarios_unsold: int = 0
        self.scenarios_to_pilots: int = 0
        self.pilot_revenue: float = 0.0
        self.cash_balance: float = cfg.starting_cash_usd
        self.fixed_monthly_burn: float = cfg.fixed_monthly_burn_usd
        self._counter: int = 0
        self._last_day: int = -1
        # Track delivered quality over a rolling window for conversion modelling.
        self._recent_qualities: list[float] = []

    # -- per-second integration ----------------------------------------------

    def maybe_tick_day(self, t_s: float) -> None:
        day = int(t_s / 86400.0)
        while self._last_day < day:
            self._last_day += 1
            self._tick_one_day(self._last_day * 86400.0)

    def _tick_one_day(self, day_t_s: float) -> None:
        # 1. Prospect arrivals (Poisson by month, sampled daily).
        per_day_rate = self.cfg.prospect_arrival_per_month / 30.0
        # Allow multiple arrivals per day with simple loop.
        arrivals = self._poisson(per_day_rate)
        for _ in range(arrivals):
            self._add_prospect(day_t_s)

        # 2. Conversion check on existing prospects.
        recent_q = self._recent_quality_mean()
        survivors: list[Prospect] = []
        for p in self.prospects:
            if day_t_s >= p.expires_at_s:
                self.expired_prospects += 1
                continue
            if recent_q < p.quality_threshold_required:
                survivors.append(p)
                continue
            # Daily conversion probability — calibrated so most prospects
            # convert within their lifetime if data quality is OK.
            if self.rng.random() < self.cfg.daily_conversion_prob:
                self._convert(p, day_t_s)
            else:
                survivors.append(p)
        self.prospects = survivors

        # 3. Daily burn accrual.
        self.cash_balance -= self.fixed_monthly_burn / 30.0

    def _add_prospect(self, t_s: float) -> None:
        self._counter += 1
        name = self.rng.choice(_PROSPECT_NAMES)
        self.prospects.append(Prospect(
            prospect_id=f"prospect_{self._counter:03d}",
            name=name,
            arrived_at_s=t_s,
            expires_at_s=t_s + self.cfg.prospect_lifetime_days * 86400.0,
            quality_threshold_required=self.rng.uniform(
                self.cfg.prospect_quality_min, self.cfg.prospect_quality_max,
            ),
        ))

    def _convert(self, prospect: Prospect, t_s: float) -> None:
        # Volume tier — spec §4.2.
        committed = self.rng.randint(
            self.cfg.scenarios_per_pilot_min,
            self.cfg.scenarios_per_pilot_max,
        )
        if committed >= 1000:
            price = 100.0
        elif committed >= 500:
            price = 150.0
        elif committed >= 100:
            price = 200.0
        else:
            price = 250.0
        self.pilots.append(Pilot(
            pilot_id=f"pilot_{len(self.pilots) + 1:02d}",
            name=prospect.name,
            signed_at_s=t_s,
            scenarios_committed=committed,
            price_per_scenario=price,
        ))

    # -- per-delivery hook ---------------------------------------------------

    def allocate_delivery(self, quality_score: float) -> Optional[Pilot]:
        """Allocate a delivered scenario to the oldest unfulfilled pilot.

        Returns the pilot (and bills them) or None if no demand.
        """
        self._recent_qualities.append(quality_score)
        if len(self._recent_qualities) > 40:
            self._recent_qualities = self._recent_qualities[-40:]
        for pilot in self.pilots:
            if not pilot.is_fulfilled:
                pilot.scenarios_delivered += 1
                if pilot.is_fulfilled:
                    pilot.closed_at_s = self._last_day * 86400.0
                self.cash_balance += pilot.price_per_scenario
                self.pilot_revenue += pilot.price_per_scenario
                self.scenarios_to_pilots += 1
                return pilot
        self.scenarios_unsold += 1
        return None

    # -- helpers -------------------------------------------------------------

    def _recent_quality_mean(self) -> float:
        if not self._recent_qualities:
            # Bootstrap — assume we can claim the spec target until proven otherwise.
            return 85.0
        return sum(self._recent_qualities) / len(self._recent_qualities)

    def _poisson(self, rate: float) -> int:
        """Sample from Poisson(rate). For small rates this is fine; we typically
        have rate << 1 (less than one arrival per day on average)."""
        # Inverse-transform: count threshold crossings of a unit exponential.
        import math
        L = math.exp(-rate)
        k, p = 0, 1.0
        while True:
            k += 1
            p *= self.rng.random()
            if p < L:
                return k - 1

    def state(self) -> FunnelState:
        committed = sum(p.scenarios_committed for p in self.pilots)
        delivered = sum(p.scenarios_delivered for p in self.pilots)
        fulfilled = sum(1 for p in self.pilots if p.is_fulfilled)
        active = len(self.pilots) - fulfilled

        elapsed_months = max(1.0 / 30.0, (self._last_day + 1) / 30.0)
        revenue_rate = self.pilot_revenue / elapsed_months
        net_burn = self.fixed_monthly_burn - revenue_rate
        if net_burn <= 0:
            runway = float("inf") if self.cash_balance > 0 else 0.0
        else:
            runway = self.cash_balance / net_burn
        return FunnelState(
            prospects_active=len(self.prospects),
            prospects_lifetime=self._counter,
            pilots_active=active,
            pilots_fulfilled=fulfilled,
            scenarios_committed=committed,
            scenarios_delivered_to_pilots=delivered,
            scenarios_unsold=self.scenarios_unsold,
            revenue_usd=self.pilot_revenue,
            cash_usd=self.cash_balance,
            monthly_burn_usd=self.fixed_monthly_burn,
            monthly_revenue_rate_usd=revenue_rate,
            runway_months=runway,
        )
