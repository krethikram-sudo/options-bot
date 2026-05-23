"""Unit economics tracker (spec 9.3 / Section 4)."""
from __future__ import annotations

from dataclasses import dataclass

from .config import EconomicsConfig


@dataclass
class EconomicsLedger:
    revenue_usd: float = 0.0
    cloud_cost_usd: float = 0.0
    drone_wear_cost_usd: float = 0.0
    operator_cost_usd: float = 0.0
    vehicle_cost_usd: float = 0.0
    overhead_cost_usd: float = 0.0
    scenarios_delivered: int = 0

    @property
    def total_variable_cost(self) -> float:
        return self.cloud_cost_usd + self.drone_wear_cost_usd

    @property
    def total_cost(self) -> float:
        return (
            self.total_variable_cost
            + self.operator_cost_usd
            + self.vehicle_cost_usd
            + self.overhead_cost_usd
        )

    @property
    def gross_profit(self) -> float:
        return self.revenue_usd - self.total_cost

    @property
    def gross_margin(self) -> float:
        if self.revenue_usd <= 0:
            return 0.0
        return self.gross_profit / self.revenue_usd


class Economics:
    def __init__(self, cfg: EconomicsConfig, host_vehicle_count: int):
        self.cfg = cfg
        self.vehicle_count = host_vehicle_count
        self.ledger = EconomicsLedger()
        # Apply fixed daily overhead as a constant accrual; spread over 24h.
        self._overhead_per_second = cfg.fixed_daily_overhead_usd / 86400.0

    def tick(self, dt: float, operating: bool) -> None:
        # Per-hour costs only while operating (daylight).
        # Spec 5.4 assumes one operator per host vehicle, so both costs scale with fleet size.
        if operating:
            self.ledger.operator_cost_usd += (
                self.cfg.operator_cost_per_hour_usd / 3600.0
            ) * dt * self.vehicle_count
            self.ledger.vehicle_cost_usd += (
                self.cfg.vehicle_cost_per_hour_usd / 3600.0
            ) * dt * self.vehicle_count
        self.ledger.overhead_cost_usd += self._overhead_per_second * dt

    def record_delivery(self) -> None:
        self.ledger.revenue_usd += self.cfg.price_per_scenario_usd
        self.ledger.cloud_cost_usd += self.cfg.cloud_cost_per_scenario_usd
        self.ledger.drone_wear_cost_usd += self.cfg.drone_wear_per_scenario_usd
        self.ledger.scenarios_delivered += 1
