"""Dock physical model — tolerance + latch mechanics.

The dock sits on the host vehicle's roof. Successful landing requires
the drone to arrive within a horizontal tolerance, descend slowly enough,
and have the host vehicle within the operational envelope (spec §1.2).
Wind degrades latch success probabilistically.

The model is intentionally simple — enough to surface failure modes that
otherwise stay hidden behind a flat 0.5% recovery_success roll.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class DockConfig:
    horizontal_tolerance_m: float = 1.5     # precision-landing pad funnel + BLE guide
    safe_descent_mps: float = 1.2           # gentle touchdown
    wind_degradation_per_mph_above_10: float = 0.012   # latch reliability cost


def latch_success_probability(
    cfg: DockConfig,
    drone_x: float,
    drone_y: float,
    drone_vz: float,
    dock_x: float,
    dock_y: float,
    vehicle_speed_mph: float,
    wind_mph: float,
    base_recovery_prob: float,
) -> float:
    """Probability that the dock latches the drone, given approach geometry + conditions.

    Failure modes baked in:
      - Misalignment beyond tolerance → drone bounces off the pad
      - Excessive descent speed → bounce / overshoot
      - High wind → mechanical reliability degrades
      - Vehicle still moving above 5 mph → spec §1.2 V1 envelope violation
    """
    d = math.hypot(drone_x - dock_x, drone_y - dock_y)
    if d > cfg.horizontal_tolerance_m * 6.0:
        # Too far off-center to even attempt — definite miss.
        return 0.0
    if d > cfg.horizontal_tolerance_m:
        # Outside the funnel but close — the BLE precision approach can sometimes recover.
        misalignment_penalty = 0.5 * (d - cfg.horizontal_tolerance_m) / cfg.horizontal_tolerance_m
    else:
        misalignment_penalty = 0.0

    descent_penalty = 0.0
    if abs(drone_vz) > cfg.safe_descent_mps:
        descent_penalty = min(0.6, (abs(drone_vz) - cfg.safe_descent_mps) * 0.2)

    envelope_penalty = 0.0
    if vehicle_speed_mph > 5.0:
        # V1 only certified for stationary or <5 mph — spec §1.2 row 3.
        envelope_penalty = min(0.9, (vehicle_speed_mph - 5.0) * 0.08)

    wind_penalty = max(0.0, wind_mph - 10.0) * cfg.wind_degradation_per_mph_above_10

    p = base_recovery_prob - misalignment_penalty - descent_penalty - envelope_penalty - wind_penalty
    return max(0.0, min(1.0, p))
