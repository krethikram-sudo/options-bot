"""World geometry — operating corridor and scenario waypoints."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


# Spec 3.5 scenario taxonomy — used to label waypoints for trigger classification.
WAYPOINT_LABELS = [
    "intersection_signalized",
    "unprotected_left_turn",
    "merge_arterial",
    "school_zone",
    "intersection_unsignalized",
    "construction_zone",
    "pedestrian_crosswalk",
    "merge_highway",
    "lane_change_complex",
    "vru_interaction",
]


@dataclass
class Waypoint:
    x: float
    y: float
    label: str
    waypoint_idx: int


def generate_corridor(
    width_m: float,
    height_m: float,
    n_waypoints: int = 10,
    rng: random.Random | None = None,
) -> list[Waypoint]:
    """A closed-loop corridor with N interesting scenario points around an oval."""
    rng = rng or random.Random()
    cx, cy = width_m / 2, height_m / 2
    rx, ry = width_m * 0.36, height_m * 0.36
    waypoints: list[Waypoint] = []
    for i in range(n_waypoints):
        theta = 2 * math.pi * i / n_waypoints
        x = cx + rx * math.cos(theta) + rng.uniform(-180, 180)
        y = cy + ry * math.sin(theta) + rng.uniform(-180, 180)
        label = WAYPOINT_LABELS[i % len(WAYPOINT_LABELS)]
        waypoints.append(Waypoint(x=x, y=y, label=label, waypoint_idx=i))
    return waypoints
