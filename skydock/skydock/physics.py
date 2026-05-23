"""Light flight dynamics — point-mass drone with momentum, wind coupling,
and bounded climb / horizontal speeds. Not a quadrotor sim; just enough
physics to make stage transitions emergent and motion look credible in
the animation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class FlightDynamics:
    """3D point-mass with proportional velocity control toward a target.

    The mission controller writes (target_x, target_y, target_z); this body
    integrates one timestep toward that target, bounded by max climb /
    horizontal speed, with a horizontal wind force coupling.
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0

    # DJI Mini 4 Pro-ish performance envelope.
    mass_kg: float = 0.249
    max_horizontal_speed_mps: float = 16.0
    max_vertical_speed_mps: float = 5.0
    accel_gain: float = 2.0           # how fast velocity tracks the setpoint
    wind_coupling_mps_per_mph: float = 0.18  # 20mph wind → ~3.6 m/s steady push

    def at_target(self, horizontal_tol_m: float = 1.5,
                  vertical_tol_m: float = 1.0) -> bool:
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dz = self.target_z - self.z
        return (math.hypot(dx, dy) < horizontal_tol_m
                and abs(dz) < vertical_tol_m)

    def step(self, dt: float, wind_mph: float, wind_dir_rad: float) -> None:
        """Integrate one timestep toward the current target."""
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dz = self.target_z - self.z
        h_dist = math.hypot(dx, dy)

        # Desired velocity = proportional approach, capped by max speeds.
        if h_dist > 0.05:
            v_target_h = min(self.max_horizontal_speed_mps, h_dist * 1.5)
            desired_vx = (dx / h_dist) * v_target_h
            desired_vy = (dy / h_dist) * v_target_h
        else:
            desired_vx = desired_vy = 0.0
        if abs(dz) > 0.05:
            # Slow descent near the ground — cap vertical speed by a near-ground
            # factor so terminal descent is gentle enough for the dock to latch.
            near_ground = max(0.15, min(1.0, self.z / 12.0))
            max_v = self.max_vertical_speed_mps * (near_ground if dz < 0 else 1.0)
            desired_vz = math.copysign(min(max_v, abs(dz) * 1.5), dz)
        else:
            desired_vz = 0.0

        # First-order approach to desired velocity (bounded acceleration).
        # Below 10m we're in "precision landing" mode (vision + BLE beacon
        # guidance kicks in): gain doubles, wind coupling halves.
        precision = self.z < 10.0
        gain = self.accel_gain * (2.0 if precision else 1.0)
        alpha = _clamp(dt * gain, 0.0, 1.0)
        self.vx += (desired_vx - self.vx) * alpha
        self.vy += (desired_vy - self.vy) * alpha
        self.vz += (desired_vz - self.vz) * alpha

        # Horizontal wind disturbance — steady-state push on the airframe.
        wind_coupling = self.wind_coupling_mps_per_mph * (0.5 if precision else 1.0)
        wind_vx = wind_mph * wind_coupling * math.cos(wind_dir_rad)
        wind_vy = wind_mph * wind_coupling * math.sin(wind_dir_rad)

        # Integrate.
        self.x += (self.vx + wind_vx) * dt
        self.y += (self.vy + wind_vy) * dt
        self.z += self.vz * dt
        if self.z < 0.0:
            self.z = 0.0
            self.vz = max(0.0, self.vz)

    def snap_to(self, x: float, y: float, z: float) -> None:
        """Place the body instantaneously (used when docked / unit returns online)."""
        self.x, self.y, self.z = x, y, z
        self.vx = self.vy = self.vz = 0.0
        self.target_x, self.target_y, self.target_z = x, y, z

    def thrust_effort_fraction(self) -> float:
        """Rough proxy for thrust effort, 0 (hover) to 1 (full draw).

        Used by the battery drain model. Climbing / fighting wind costs more.
        """
        # Vertical effort: pulling against gravity. ~0.6 baseline for hover.
        climb_factor = 0.6 + max(0.0, self.vz) * 0.08
        # Horizontal effort: proportional to horizontal speed (drag-limited).
        h_speed = math.hypot(self.vx, self.vy)
        return _clamp(climb_factor + h_speed * 0.025, 0.4, 1.0)
