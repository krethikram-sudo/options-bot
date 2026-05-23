"""World geometry — operating corridor and scenario waypoints.

The corridor is a closed loop of axis-aligned segments (a city-block tour),
so host vehicles drive straight, turn at corners, and the route reads as
streets rather than a geometric oval.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


# Spec 3.5 scenario taxonomy — labels assigned in route order.
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
    """A closed-loop tour with axis-aligned segments — like a city block route.

    Builds the loop on a 3-column × 3-row grid (skipping the centre), so all
    connections between consecutive waypoints are horizontal or vertical.
    Extra interior waypoints are inserted on long edges so the route has the
    target waypoint count.
    """
    rng = rng or random.Random()
    margin_x = width_m * 0.12
    margin_y = height_m * 0.12
    inner_x = width_m * 0.5
    inner_y = height_m * 0.5

    # Base perimeter tour (clockwise from SE) — 8 corners + midpoints, all axis-aligned.
    base = [
        (width_m - margin_x, margin_y),             # SE corner
        (width_m - margin_x, inner_y),              # E-mid
        (width_m - margin_x, height_m - margin_y),  # NE corner
        (inner_x, height_m - margin_y),             # N-mid
        (margin_x, height_m - margin_y),            # NW corner
        (margin_x, inner_y),                        # W-mid
        (margin_x, margin_y),                       # SW corner
        (inner_x, margin_y),                        # S-mid
    ]

    points = list(base)
    while len(points) < n_waypoints:
        # Split the currently-longest segment by inserting its midpoint.
        longest_i = 0
        longest_d = 0.0
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            d = abs(x2 - x1) + abs(y2 - y1)
            if d > longest_d:
                longest_d = d
                longest_i = i
        x1, y1 = points[longest_i]
        x2, y2 = points[(longest_i + 1) % len(points)]
        midpoint = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        points.insert(longest_i + 1, midpoint)

    points = points[:n_waypoints]

    # Small jitter along the segment direction so the loop doesn't look mechanical.
    waypoints: list[Waypoint] = []
    for i, (x, y) in enumerate(points):
        nx, ny = points[(i + 1) % len(points)]
        if abs(nx - x) > abs(ny - y):
            x += rng.uniform(-40, 40)
        else:
            y += rng.uniform(-40, 40)
        label = WAYPOINT_LABELS[i % len(WAYPOINT_LABELS)]
        waypoints.append(Waypoint(x=x, y=y, label=label, waypoint_idx=i))
    return waypoints
