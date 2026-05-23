"""Host vehicle — follows the corridor loop, stops briefly at waypoints."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .world import Waypoint


@dataclass
class HostVehicle:
    vehicle_id: str
    waypoints: list[Waypoint]
    speed_mps: float
    x: float = 0.0
    y: float = 0.0
    heading_rad: float = 0.0
    target_idx: int = 0
    stopped: bool = False
    stop_seconds_remaining: float = 0.0
    distance_driven_m: float = 0.0

    def __post_init__(self) -> None:
        if self.waypoints:
            self.x = self.waypoints[0].x
            self.y = self.waypoints[0].y
            self.target_idx = 1 % len(self.waypoints)

    @property
    def speed_mph(self) -> float:
        return self.speed_mps * 2.23694

    @property
    def target_waypoint(self) -> Waypoint:
        return self.waypoints[self.target_idx % len(self.waypoints)]

    @property
    def last_passed_waypoint(self) -> Waypoint:
        return self.waypoints[(self.target_idx - 1) % len(self.waypoints)]

    def stop_for(self, seconds: float) -> None:
        self.stopped = True
        self.stop_seconds_remaining = max(self.stop_seconds_remaining, seconds)

    def update(self, dt: float) -> Waypoint | None:
        """Advance one tick. Returns the waypoint just reached (if any)."""
        if self.stopped:
            self.stop_seconds_remaining -= dt
            if self.stop_seconds_remaining <= 0:
                self.stopped = False
            return None

        wp = self.target_waypoint
        dx = wp.x - self.x
        dy = wp.y - self.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            reached = wp
            self.target_idx = (self.target_idx + 1) % len(self.waypoints)
            return reached

        step = self.speed_mps * dt
        if step >= d:
            self.x, self.y = wp.x, wp.y
            self.distance_driven_m += d
            reached = wp
            self.target_idx = (self.target_idx + 1) % len(self.waypoints)
            return reached
        else:
            self.x += step * dx / d
            self.y += step * dy / d
            self.heading_rad = math.atan2(dy, dx)
            self.distance_driven_m += step
            return None
