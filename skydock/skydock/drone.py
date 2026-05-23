"""Drone — physical state. Position/velocity owned by a FlightDynamics body."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from .physics import FlightDynamics
from .scene import fov_footprint_radius_m


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
    physics: FlightDynamics = field(default_factory=FlightDynamics)
    battery_pct: float = 100.0
    battery_capacity_pct: float = 100.0    # degrades over flight cycles
    flight_count: int = 0
    fov_diag_deg: float = 80.0             # camera diagonal field of view

    # -- position shims so existing code keeps working --------------------

    @property
    def x(self) -> float:
        return self.physics.x

    @x.setter
    def x(self, value: float) -> None:
        self.physics.x = value

    @property
    def y(self) -> float:
        return self.physics.y

    @y.setter
    def y(self, value: float) -> None:
        self.physics.y = value

    @property
    def altitude_m(self) -> float:
        return self.physics.z

    @altitude_m.setter
    def altitude_m(self, value: float) -> None:
        self.physics.z = value

    @property
    def coverage_radius_m(self) -> float:
        return fov_footprint_radius_m(self.altitude_m, self.fov_diag_deg)

    # -- state helpers -----------------------------------------------------

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
            # ~60 min empty → full when docked.
            self.battery_pct = min(
                self.battery_capacity_pct,
                self.battery_pct + (100.0 / 3600.0) * dt,
            )
        elif self.is_airborne:
            # ~34 min flight time at full thrust effort; less when hovering.
            effort = self.physics.thrust_effort_fraction()
            self.battery_pct = max(0.0, self.battery_pct
                                   - (100.0 / (34 * 60)) * effort * dt)

    def register_flight_complete(self, capacity_loss_pct: float) -> None:
        """Mark a completed flight cycle and degrade max battery capacity."""
        self.flight_count += 1
        self.battery_capacity_pct = max(60.0, self.battery_capacity_pct - capacity_loss_pct)
        if self.battery_pct > self.battery_capacity_pct:
            self.battery_pct = self.battery_capacity_pct
