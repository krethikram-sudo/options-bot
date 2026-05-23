"""Ground traffic scene + FOV projection (spec §1.1 capture phase made concrete).

When a mission enters CAPTURING, a TrafficScene is spawned around the
capture point with realistic agents (cars on roads, peds at crosswalks,
cyclists) appropriate to the waypoint's scene class. Each animation
frame, the drone's camera footprint is computed from its altitude and
FOV; agents inside the footprint that frame are logged as "visible".
Capture quality is derived from visibility coverage instead of being
drawn from a Gaussian.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


# Per-scene-class agent densities (vehicles, pedestrians, cyclists) and
# typical speed ranges. Loosely calibrated to feel right for the spec's
# scenario taxonomy (§3.5) rather than to any real traffic model.
SCENE_TEMPLATES: dict[str, dict] = {
    "intersection_signalized":   dict(veh=10, ped=14, cyc=2, veh_speed=(1.5, 10), road_axes=("ns", "ew")),
    "intersection_unsignalized": dict(veh=6,  ped=8,  cyc=1, veh_speed=(1.0, 8),  road_axes=("ns", "ew")),
    "unprotected_left_turn":     dict(veh=9,  ped=16, cyc=2, veh_speed=(1.0, 9),  road_axes=("ns", "ew")),
    "school_zone":               dict(veh=4,  ped=22, cyc=1, veh_speed=(2.0, 6),  road_axes=("ew",)),
    "pedestrian_crosswalk":      dict(veh=3,  ped=18, cyc=2, veh_speed=(0.0, 4),  road_axes=("ew",)),
    "construction_zone":         dict(veh=5,  ped=4,  cyc=1, veh_speed=(2.0, 7),  road_axes=("ew",)),
    "merge_arterial":            dict(veh=12, ped=2,  cyc=2, veh_speed=(6.0, 14), road_axes=("ew",)),
    "merge_highway":             dict(veh=16, ped=0,  cyc=0, veh_speed=(15.0, 28),road_axes=("ew",)),
    "lane_change_complex":       dict(veh=10, ped=1,  cyc=1, veh_speed=(8.0, 18), road_axes=("ew",)),
    "vru_interaction":           dict(veh=5,  ped=8,  cyc=4, veh_speed=(2.0, 8),  road_axes=("ns", "ew")),
}


_AGENT_COLORS = {
    "passenger_vehicle": "#7ab0d4",
    "pedestrian": "#9ee37d",
    "cyclist": "#e5b85a",
}


@dataclass
class TrafficAgent:
    agent_id: str
    cls: str
    x0: float
    y0: float
    heading_rad: float
    speed_mps: float
    bbox: tuple[float, float, float]
    spawned_t_s: float

    def position_at(self, t_offset: float) -> tuple[float, float]:
        return (self.x0 + math.cos(self.heading_rad) * self.speed_mps * t_offset,
                self.y0 + math.sin(self.heading_rad) * self.speed_mps * t_offset)


@dataclass
class TrafficScene:
    scene_class: str
    center_x: float
    center_y: float
    radius_m: float
    spawned_at_s: float
    agents: list[TrafficAgent] = field(default_factory=list)
    # Per-agent set of frame indices where the agent was inside the FOV footprint.
    visibility: dict[str, set[int]] = field(default_factory=dict)
    frames_observed: int = 0

    def agent_color(self, agent_id: str) -> str:
        for a in self.agents:
            if a.agent_id == agent_id:
                return _AGENT_COLORS.get(a.cls, "#aaaaaa")
        return "#aaaaaa"

    def positions_now(self, t_s: float) -> list[tuple[str, str, float, float]]:
        """Returns (agent_id, class, x, y) tuples for every agent at sim time t_s."""
        out = []
        for a in self.agents:
            x, y = a.position_at(t_s - a.spawned_t_s)
            out.append((a.agent_id, a.cls, x, y))
        return out

    def record_observation(self, frame_idx: int, visible_agent_ids: set[str]) -> None:
        self.frames_observed = max(self.frames_observed, frame_idx + 1)
        for aid in visible_agent_ids:
            self.visibility.setdefault(aid, set()).add(frame_idx)

    def visibility_summary(self) -> dict[str, float]:
        """Per-agent visibility ratio (frames seen / total frames)."""
        if self.frames_observed == 0:
            return {}
        return {aid: len(frames) / self.frames_observed
                for aid, frames in self.visibility.items()}

    def derived_quality_score(self) -> float:
        """Map visibility coverage + agent diversity → 0..100 quality score.

        Weighted blend:
          - 60 pts from average visibility ratio of agents that were seen at all
          - 20 pts from how many of the spawned agents were seen at any point
          - 20 pts from class diversity (vehicle + ped + cyclist all present)
        """
        if not self.agents or self.frames_observed == 0:
            return 0.0
        summary = self.visibility_summary()

        if summary:
            avg_visibility = sum(summary.values()) / len(summary)
        else:
            avg_visibility = 0.0
        visibility_pts = 60.0 * avg_visibility

        coverage_ratio = len(summary) / len(self.agents)
        coverage_pts = 20.0 * coverage_ratio

        seen_classes = {a.cls for a in self.agents if a.agent_id in summary}
        diversity_pts = 20.0 * len(seen_classes) / 3.0  # 3 classes possible

        return max(0.0, min(100.0, visibility_pts + coverage_pts + diversity_pts))


class SceneGenerator:
    """Spawns realistic agents for a given scene class around a capture centre."""

    def __init__(self, rng: random.Random, area_radius_m: float = 90.0):
        self.rng = rng
        self.area_radius_m = area_radius_m
        self._counter = 0

    def generate(
        self, scene_class: str, center_x: float, center_y: float, t_s: float,
    ) -> TrafficScene:
        tpl = SCENE_TEMPLATES.get(scene_class) or SCENE_TEMPLATES["intersection_signalized"]
        scene = TrafficScene(
            scene_class=scene_class,
            center_x=center_x, center_y=center_y,
            radius_m=self.area_radius_m,
            spawned_at_s=t_s,
        )
        for _ in range(tpl["veh"]):
            scene.agents.append(self._spawn_vehicle(center_x, center_y, t_s, tpl))
        for _ in range(tpl["ped"]):
            scene.agents.append(self._spawn_pedestrian(center_x, center_y, t_s))
        for _ in range(tpl["cyc"]):
            scene.agents.append(self._spawn_cyclist(center_x, center_y, t_s, tpl))
        return scene

    # -- spawning helpers ----------------------------------------------------

    def _spawn_vehicle(self, cx: float, cy: float, t_s: float, tpl: dict) -> TrafficAgent:
        # Vehicles travel along a road axis at scene-typical speed.
        axis = self.rng.choice(tpl["road_axes"])
        speed = self.rng.uniform(*tpl["veh_speed"])
        if axis == "ns":
            # N or S bound
            heading = math.pi / 2 if self.rng.random() < 0.5 else -math.pi / 2
            x = cx + self.rng.uniform(-6, 6)
            y = cy + self.rng.uniform(-self.area_radius_m * 0.8, self.area_radius_m * 0.8)
        else:
            heading = 0.0 if self.rng.random() < 0.5 else math.pi
            x = cx + self.rng.uniform(-self.area_radius_m * 0.8, self.area_radius_m * 0.8)
            y = cy + self.rng.uniform(-6, 6)
        self._counter += 1
        return TrafficAgent(
            agent_id=f"veh_{self._counter:04d}",
            cls="passenger_vehicle",
            x0=x, y0=y, heading_rad=heading, speed_mps=speed,
            bbox=(4.6, 1.8, 1.5),
            spawned_t_s=t_s,
        )

    def _spawn_pedestrian(self, cx: float, cy: float, t_s: float) -> TrafficAgent:
        # Peds wander randomly within a tighter circle near road intersections.
        r = self.rng.uniform(8, self.area_radius_m * 0.7)
        theta = self.rng.uniform(0, 2 * math.pi)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        heading = self.rng.uniform(0, 2 * math.pi)
        speed = self.rng.uniform(0.8, 1.8)
        self._counter += 1
        return TrafficAgent(
            agent_id=f"ped_{self._counter:04d}",
            cls="pedestrian",
            x0=x, y0=y, heading_rad=heading, speed_mps=speed,
            bbox=(0.5, 0.5, 1.7),
            spawned_t_s=t_s,
        )

    def _spawn_cyclist(self, cx: float, cy: float, t_s: float, tpl: dict) -> TrafficAgent:
        # Cyclists travel along a road axis at moderate speed.
        axis = self.rng.choice(tpl["road_axes"])
        speed = self.rng.uniform(2.5, 6.0)
        if axis == "ns":
            heading = math.pi / 2 if self.rng.random() < 0.5 else -math.pi / 2
            x = cx + self.rng.uniform(-12, 12)
            y = cy + self.rng.uniform(-self.area_radius_m * 0.8, self.area_radius_m * 0.8)
        else:
            heading = 0.0 if self.rng.random() < 0.5 else math.pi
            x = cx + self.rng.uniform(-self.area_radius_m * 0.8, self.area_radius_m * 0.8)
            y = cy + self.rng.uniform(-12, 12)
        self._counter += 1
        return TrafficAgent(
            agent_id=f"cyc_{self._counter:04d}",
            cls="cyclist",
            x0=x, y0=y, heading_rad=heading, speed_mps=speed,
            bbox=(1.7, 0.6, 1.6),
            spawned_t_s=t_s,
        )


# -- FOV projection ----------------------------------------------------------

def fov_footprint_radius_m(altitude_m: float, fov_diag_deg: float = 80.0) -> float:
    """Ground radius of a downward-pointing camera's footprint.

    Assumes gimbal straight down (90° pitch). For altitude h and diagonal FOV
    alpha, ground footprint radius = h * tan(alpha / 2).
    """
    return max(0.0, altitude_m) * math.tan(math.radians(fov_diag_deg / 2.0))


def agents_in_footprint(
    drone_x: float, drone_y: float, footprint_radius_m: float,
    agents_positions: list[tuple[str, str, float, float]],
) -> set[str]:
    """Returns the set of agent_ids within the circular ground footprint."""
    out: set[str] = set()
    r2 = footprint_radius_m * footprint_radius_m
    for aid, _cls, x, y in agents_positions:
        dx, dy = x - drone_x, y - drone_y
        if dx * dx + dy * dy <= r2:
            out.add(aid)
    return out
