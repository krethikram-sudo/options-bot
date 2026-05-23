"""Drone — physical state owned and stepped by the mission controller."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class DroneState(Enum):
    DOCKED = auto()
    PRE_FLIGHT = auto()
    LAUNCHING = auto()
    CLIMBING = auto()
    CAPTURING = auto()
    RETURNING = auto()
    LANDING = auto()
    LOST = auto()


@dataclass
class Drone:
    drone_id: str
    state: DroneState = DroneState.DOCKED
    x: float = 0.0
    y: float = 0.0
    altitude_m: float = 0.0
    battery_pct: float = 100.0
    coverage_radius_m: float = 110.0   # ~80m alt + 50deg FOV gives ~70-110m ground radius

    @property
    def is_airborne(self) -> bool:
        return self.state in (
            DroneState.LAUNCHING,
            DroneState.CLIMBING,
            DroneState.CAPTURING,
            DroneState.RETURNING,
            DroneState.LANDING,
        )

    @property
    def is_busy(self) -> bool:
        return self.state not in (DroneState.DOCKED, DroneState.LOST)

    def charge_or_drain(self, dt: float) -> None:
        if self.state == DroneState.DOCKED:
            # ~60 min from empty to full.
            self.battery_pct = min(100.0, self.battery_pct + (100.0 / 3600.0) * dt)
        elif self.is_airborne:
            # ~34 min flight time at full draw.
            self.battery_pct = max(0.0, self.battery_pct - (100.0 / (34 * 60)) * dt)
