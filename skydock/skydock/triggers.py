"""Trigger generation — Poisson arrivals + waypoint and hard-brake events (spec 1.3)."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .config import TriggerConfig
from .vehicle import HostVehicle
from .world import Waypoint


@dataclass
class Trigger:
    trigger_id: str
    type: str            # 'manual', 'waypoint', 'hard_brake'
    waypoint: Waypoint
    t_s: float


class TriggerGenerator:
    """Poisson trigger source. Each trigger pulls a host vehicle's nearest waypoint as its scene anchor."""

    def __init__(self, cfg: TriggerConfig, waypoints: list[Waypoint], rng: random.Random):
        self.cfg = cfg
        self.waypoints = waypoints
        self.rng = rng
        self._counter = 0
        self._visited_in_lap: set[int] = set()

    def poll(
        self,
        dt: float,
        t_s: float,
        vehicle: HostVehicle,
        rate_multiplier: float = 1.0,
    ) -> Trigger | None:
        # Trigger probability per dt = rate per hour * rate_multiplier * dt / 3600.
        p = self.cfg.poisson_rate_per_hour * rate_multiplier * dt / 3600.0
        if self.rng.random() >= p:
            return None
        return self._make_trigger(t_s, vehicle)

    def trigger_on_waypoint(self, t_s: float, vehicle: HostVehicle, wp: Waypoint) -> Trigger | None:
        """Pre-planned waypoint trigger — fires when the vehicle reaches a fresh waypoint.

        Each waypoint is triggerable once per lap; the lap resets automatically
        when the vehicle has visited every waypoint at least once.
        """
        if len(self._visited_in_lap) >= len(self.waypoints):
            self._visited_in_lap.clear()
        if wp.waypoint_idx in self._visited_in_lap:
            return None
        # Mark visited so the lap can complete regardless of whether this
        # particular waypoint fires.
        self._visited_in_lap.add(wp.waypoint_idx)
        if self.rng.random() < self.cfg.waypoint_trigger_prob:
            return self._make_trigger(t_s, vehicle, force_type="waypoint", wp=wp)
        return None

    def reset_lap(self) -> None:
        self._visited_in_lap.clear()

    def _make_trigger(
        self,
        t_s: float,
        vehicle: HostVehicle,
        force_type: str | None = None,
        wp: Waypoint | None = None,
    ) -> Trigger:
        self._counter += 1
        if force_type:
            ttype = force_type
        else:
            # Poisson source covers manual + hard_brake only — waypoint
            # triggers have their own source (`trigger_on_waypoint`).
            r = self.rng.random()
            ttype = "manual" if r < self.cfg.manual_share else "hard_brake"
        scene = wp or self._nearest_waypoint(vehicle.x, vehicle.y)
        return Trigger(
            trigger_id=f"trg_{self._counter:05d}",
            type=ttype,
            waypoint=scene,
            t_s=t_s,
        )

    def _nearest_waypoint(self, x: float, y: float) -> Waypoint:
        return min(self.waypoints, key=lambda w: (w.x - x) ** 2 + (w.y - y) ** 2)
