"""World geometry — operating corridors with type-specific scene mixes.

Each corridor is a closed-loop tour of axis-aligned segments confined to
a bounding box on the world map, so multiple corridors can coexist
without overlapping. Corridor types differ in:

  - layout (city block vs straight artery vs sparse residential)
  - waypoint scene-class mix (spec §3.5)
  - intrinsic Poisson trigger multiplier (urban dense > suburban > highway)
"""
from __future__ import annotations

import random
from dataclasses import dataclass


# Per-type scene mixes, drawn from spec §3.5 scenario taxonomy.
CORRIDOR_SCENE_MIX = {
    "urban_dense": [
        "intersection_signalized",
        "unprotected_left_turn",
        "pedestrian_crosswalk",
        "vru_interaction",
        "intersection_unsignalized",
        "lane_change_complex",
        "construction_zone",
        "unprotected_left_turn",
        "pedestrian_crosswalk",
        "intersection_signalized",
    ],
    "suburban": [
        "intersection_signalized",
        "school_zone",
        "pedestrian_crosswalk",
        "intersection_unsignalized",
        "school_zone",
        "intersection_signalized",
        "pedestrian_crosswalk",
        "intersection_unsignalized",
    ],
    "highway_mix": [
        "merge_highway",
        "merge_arterial",
        "lane_change_complex",
        "merge_highway",
        "lane_change_complex",
        "merge_arterial",
    ],
}

# Multiplier applied to the base poisson trigger rate per corridor type.
CORRIDOR_RATE_MULTIPLIER = {
    "urban_dense": 1.4,
    "suburban": 1.0,
    "highway_mix": 0.65,
}


@dataclass
class Waypoint:
    x: float
    y: float
    label: str
    waypoint_idx: int


@dataclass
class Corridor:
    name: str
    corridor_type: str
    waypoints: list[Waypoint]
    bbox: tuple[float, float, float, float]   # x0, y0, x1, y1
    rate_multiplier: float


def generate_corridor(
    bbox: tuple[float, float, float, float],
    corridor_type: str = "urban_dense",
    name: str | None = None,
    rng: random.Random | None = None,
) -> Corridor:
    """Generate a corridor confined to the given bbox with type-specific scene mix."""
    rng = rng or random.Random()
    if corridor_type == "highway_mix":
        waypoints = _generate_highway(bbox, corridor_type, rng)
    elif corridor_type == "suburban":
        waypoints = _generate_suburban(bbox, corridor_type, rng)
    else:
        waypoints = _generate_urban_block(bbox, corridor_type, rng)
    return Corridor(
        name=name or corridor_type,
        corridor_type=corridor_type,
        waypoints=waypoints,
        bbox=bbox,
        rate_multiplier=CORRIDOR_RATE_MULTIPLIER.get(corridor_type, 1.0),
    )


def split_world_into_bboxes(
    width_m: float,
    height_m: float,
    n: int,
) -> list[tuple[float, float, float, float]]:
    """Tile the world into N non-overlapping bboxes, prioritizing larger boxes.

    For 1 → full world.  2 → side-by-side.  3+ → roughly square grid.
    """
    if n <= 1:
        return [(0.0, 0.0, width_m, height_m)]
    if n == 2:
        return [
            (0.0, 0.0, width_m / 2, height_m),
            (width_m / 2, 0.0, width_m, height_m),
        ]
    # Pick grid dims that roughly preserve aspect ratio.
    import math
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    bw = width_m / cols
    bh = height_m / rows
    boxes = []
    for i in range(n):
        c = i % cols
        r = i // cols
        boxes.append((c * bw, r * bh, (c + 1) * bw, (r + 1) * bh))
    return boxes


# -- per-type generators -----------------------------------------------

def _label_for(corridor_type: str, i: int) -> str:
    mix = CORRIDOR_SCENE_MIX.get(corridor_type) or CORRIDOR_SCENE_MIX["urban_dense"]
    return mix[i % len(mix)]


def _generate_urban_block(
    bbox: tuple[float, float, float, float],
    corridor_type: str,
    rng: random.Random,
    n_waypoints: int = 10,
) -> list[Waypoint]:
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    margin_x = w * 0.14
    margin_y = h * 0.14
    inner_x = x0 + w * 0.5
    inner_y = y0 + h * 0.5
    base = [
        (x1 - margin_x, y0 + margin_y),
        (x1 - margin_x, inner_y),
        (x1 - margin_x, y1 - margin_y),
        (inner_x, y1 - margin_y),
        (x0 + margin_x, y1 - margin_y),
        (x0 + margin_x, inner_y),
        (x0 + margin_x, y0 + margin_y),
        (inner_x, y0 + margin_y),
    ]
    points = list(base)
    while len(points) < n_waypoints:
        longest_i, longest_d = 0, 0.0
        for i in range(len(points)):
            ax, ay = points[i]
            bx, by = points[(i + 1) % len(points)]
            d = abs(bx - ax) + abs(by - ay)
            if d > longest_d:
                longest_d, longest_i = d, i
        ax, ay = points[longest_i]
        bx, by = points[(longest_i + 1) % len(points)]
        points.insert(longest_i + 1, ((ax + bx) / 2.0, (ay + by) / 2.0))
    return _build_waypoints(points[:n_waypoints], corridor_type, rng, jitter=40)


def _generate_suburban(
    bbox: tuple[float, float, float, float],
    corridor_type: str,
    rng: random.Random,
    n_waypoints: int = 8,
) -> list[Waypoint]:
    """Larger sparser loop with fewer interior turns — feels like residential streets."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    margin_x = w * 0.18
    margin_y = h * 0.18
    points = [
        (x1 - margin_x, y0 + margin_y),
        (x1 - margin_x, y1 - margin_y),
        (x0 + margin_x, y1 - margin_y),
        (x0 + margin_x, y0 + margin_y),
    ]
    while len(points) < n_waypoints:
        longest_i, longest_d = 0, 0.0
        for i in range(len(points)):
            ax, ay = points[i]
            bx, by = points[(i + 1) % len(points)]
            d = abs(bx - ax) + abs(by - ay)
            if d > longest_d:
                longest_d, longest_i = d, i
        ax, ay = points[longest_i]
        bx, by = points[(longest_i + 1) % len(points)]
        points.insert(longest_i + 1, ((ax + bx) / 2.0, (ay + by) / 2.0))
    return _build_waypoints(points[:n_waypoints], corridor_type, rng, jitter=60)


def _generate_highway(
    bbox: tuple[float, float, float, float],
    corridor_type: str,
    rng: random.Random,
    n_waypoints: int = 6,
) -> list[Waypoint]:
    """A long thin out-and-back: drive the length of the bbox and come back."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    # Two parallel lanes — top going west-to-east, bottom going east-to-west.
    top_y = y0 + h * 0.35
    bot_y = y0 + h * 0.65
    margin = w * 0.10
    points = [
        (x0 + margin, bot_y),
        (x0 + margin + (w - 2 * margin) * 0.33, bot_y),
        (x0 + margin + (w - 2 * margin) * 0.66, bot_y),
        (x1 - margin, bot_y),
        (x1 - margin, top_y),
        (x0 + margin + (w - 2 * margin) * 0.5, top_y),
    ]
    points = points[:n_waypoints]
    return _build_waypoints(points, corridor_type, rng, jitter=25)


def _build_waypoints(
    points: list[tuple[float, float]],
    corridor_type: str,
    rng: random.Random,
    jitter: float,
) -> list[Waypoint]:
    waypoints: list[Waypoint] = []
    for i, (x, y) in enumerate(points):
        nx, ny = points[(i + 1) % len(points)]
        if abs(nx - x) > abs(ny - y):
            x += rng.uniform(-jitter, jitter)
        else:
            y += rng.uniform(-jitter, jitter)
        waypoints.append(Waypoint(x=x, y=y, label=_label_for(corridor_type, i),
                                   waypoint_idx=i))
    return waypoints
