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
    altitude_log: list[float] = field(default_factory=list)
    wind_log: list[float] = field(default_factory=list)
    # Traffic-light cycle. For signalized-intersection scenes, half the cycle
    # is EW-green, half is NS-green. Vehicles approaching from the red side
    # stop at the stop line.
    cycle_period_s: float = 50.0
    has_signal: bool = False
    road_axes: tuple = ("ew",)

    _STOP_LINE_M: float = 9.0

    def agent_color(self, agent_id: str) -> str:
        for a in self.agents:
            if a.agent_id == agent_id:
                return _AGENT_COLORS.get(a.cls, "#aaaaaa")
        return "#aaaaaa"

    def is_green_for(self, axis: str, t_offset_s: float) -> bool:
        """Returns whether the given road axis is green at the given offset."""
        if not self.has_signal:
            return True
        phase = (t_offset_s % self.cycle_period_s) / self.cycle_period_s
        if axis == "ew":
            return phase < 0.5
        return phase >= 0.5

    def positions_now(self, t_s: float) -> list[tuple[str, str, float, float]]:
        """Returns (agent_id, class, x, y) tuples for every agent at sim time t_s.

        Vehicles approaching a red light at a signalized intersection are
        clamped at the stop line; once their direction turns green they resume.
        """
        out = []
        for a in self.agents:
            t_offset = t_s - a.spawned_t_s
            raw_x, raw_y = a.position_at(t_offset)
            x, y = self._apply_traffic_lights(a, raw_x, raw_y, t_offset)
            out.append((a.agent_id, a.cls, x, y))
        return out

    def cull_and_respawn(self, t_s: float, generator: "SceneGenerator") -> None:
        """Replace agents that have left the scene area to keep density steady
        through long captures. Called once per observation tick."""
        replaced: list[TrafficAgent] = []
        cull_radius = self.radius_m * 1.4
        cull_sq = cull_radius * cull_radius
        for a in self.agents:
            x, y = a.position_at(t_s - a.spawned_t_s)
            x, y = self._apply_traffic_lights(a, x, y, t_s - a.spawned_t_s)
            dx = x - self.center_x
            dy = y - self.center_y
            if dx * dx + dy * dy > cull_sq:
                # Spawn a fresh agent of the same class to replace this one.
                tpl = SCENE_TEMPLATES.get(self.scene_class) or SCENE_TEMPLATES["intersection_signalized"]
                if a.cls == "passenger_vehicle":
                    fresh = generator._spawn_vehicle(self.center_x, self.center_y, t_s, tpl)
                elif a.cls == "pedestrian":
                    fresh = generator._spawn_pedestrian(self.center_x, self.center_y, t_s, tpl)
                else:
                    fresh = generator._spawn_cyclist(self.center_x, self.center_y, t_s, tpl)
                replaced.append(fresh)
            else:
                replaced.append(a)
        self.agents = replaced

    def _apply_traffic_lights(
        self, agent: TrafficAgent, raw_x: float, raw_y: float, t_offset_s: float,
    ) -> tuple[float, float]:
        if not self.has_signal or agent.cls != "passenger_vehicle":
            return raw_x, raw_y
        # Infer axis from heading.
        cos_h = math.cos(agent.heading_rad)
        sin_h = math.sin(agent.heading_rad)
        is_ew = abs(cos_h) > abs(sin_h)
        axis = "ew" if is_ew else "ns"
        if self.is_green_for(axis, t_offset_s):
            return raw_x, raw_y
        # Red — stop at the stop line if the agent would otherwise have
        # crossed past it.
        if is_ew:
            if cos_h > 0:   # east-bound
                stop_x = self.center_x - self._STOP_LINE_M
                if agent.x0 <= stop_x and raw_x > stop_x:
                    return stop_x, raw_y
            else:           # west-bound
                stop_x = self.center_x + self._STOP_LINE_M
                if agent.x0 >= stop_x and raw_x < stop_x:
                    return stop_x, raw_y
        else:
            if sin_h > 0:   # north-bound
                stop_y = self.center_y - self._STOP_LINE_M
                if agent.y0 <= stop_y and raw_y > stop_y:
                    return raw_x, stop_y
            else:           # south-bound
                stop_y = self.center_y + self._STOP_LINE_M
                if agent.y0 >= stop_y and raw_y < stop_y:
                    return raw_x, stop_y
        return raw_x, raw_y

    def record_observation(
        self,
        frame_idx: int,
        visible_agent_ids: set[str],
        drone_altitude_m: float | None = None,
        wind_mph: float | None = None,
    ) -> None:
        self.frames_observed = max(self.frames_observed, frame_idx + 1)
        for aid in visible_agent_ids:
            self.visibility.setdefault(aid, set()).add(frame_idx)
        if drone_altitude_m is not None:
            self.altitude_log.append(drone_altitude_m)
        if wind_mph is not None:
            self.wind_log.append(wind_mph)

    def visibility_summary(self) -> dict[str, float]:
        """Per-agent visibility ratio (frames seen / total frames)."""
        if self.frames_observed == 0:
            return {}
        return {aid: len(frames) / self.frames_observed
                for aid, frames in self.visibility.items()}

    def derived_quality_score(self) -> float:
        """Map visibility coverage + agent diversity → 0..100 quality score.

        Weighted blend:
          - 60 pts from average visibility ratio (frames seen / frames observed)
          - 20 pts from how many of the spawned agents were seen at any point
            (capped at 70% — realistic FOV will never cover 100% of the scene)
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

        # Coverage saturates at 70%: a single camera at altitude cannot see
        # 100% of a 90m-radius traffic scene, so capping prevents the formula
        # from penalising realistic captures for not seeing what's outside FOV.
        coverage_ratio = min(1.0, len(summary) / max(1, len(self.agents)) / 0.70)
        coverage_pts = 20.0 * coverage_ratio

        seen_classes = {a.cls for a in self.agents if a.agent_id in summary}
        # Diversity scales with expected number of classes in this scene
        # (some scenes don't have cyclists or peds at all).
        spawned_classes = {a.cls for a in self.agents}
        denom = max(1, len(spawned_classes))
        diversity_pts = 20.0 * len(seen_classes) / denom

        base_score = visibility_pts + coverage_pts + diversity_pts

        # Resolution-vs-altitude penalty: higher altitude = wider FOV but
        # smaller per-agent pixel size in the captured image, so per-agent
        # quality drops. Baseline 80m AGL gets full quality; above that the
        # score scales down.
        if self.altitude_log:
            avg_alt = sum(self.altitude_log) / len(self.altitude_log)
            if avg_alt > 80.0:
                # Linear taper: 80m → 1.0, 130m → 0.85, 180m → 0.70
                resolution_factor = max(0.6, 1.0 - (avg_alt - 80.0) / 333.0)
                base_score *= resolution_factor

        # Wind-shake penalty: high wind shakes the drone, blurring frames.
        # 0 penalty at ≤10mph, ~15% degradation at 20mph (max).
        if self.wind_log:
            avg_wind = sum(self.wind_log) / len(self.wind_log)
            wind_factor = max(0.85, 1.0 - max(0.0, avg_wind - 10.0) * 0.015)
            base_score *= wind_factor

        return max(0.0, min(100.0, base_score))


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
            has_signal=(scene_class == "intersection_signalized"),
            road_axes=tuple(tpl["road_axes"]),
        )
        for _ in range(tpl["veh"]):
            scene.agents.append(self._spawn_vehicle(center_x, center_y, t_s, tpl))
        for _ in range(tpl["ped"]):
            scene.agents.append(self._spawn_pedestrian(center_x, center_y, t_s, tpl))
        for _ in range(tpl["cyc"]):
            scene.agents.append(self._spawn_cyclist(center_x, center_y, t_s, tpl))
        self._add_class_specifics(scene, scene_class, center_x, center_y, t_s)
        return scene

    def _add_class_specifics(
        self, scene: TrafficScene, scene_class: str,
        cx: float, cy: float, t_s: float,
    ) -> None:
        """Per-scene-class signature features so each class reads differently."""
        if scene_class == "unprotected_left_turn":
            # A vehicle paused at the intersection waiting to turn left
            # across oncoming north-bound traffic.
            self._counter += 1
            scene.agents.append(TrafficAgent(
                agent_id=f"veh_{self._counter:04d}",
                cls="passenger_vehicle",
                x0=cx - self._LANE_OFFSET_M, y0=cy,
                heading_rad=math.pi / 2,
                speed_mps=0.0,
                bbox=(4.6, 1.8, 1.5),
                spawned_t_s=t_s,
            ))
        elif scene_class == "construction_zone":
            # A construction vehicle blocking one lane.
            self._counter += 1
            scene.agents.append(TrafficAgent(
                agent_id=f"veh_{self._counter:04d}",
                cls="passenger_vehicle",
                x0=cx + self.rng.uniform(-8, 8),
                y0=cy + self._LANE_OFFSET_M,
                heading_rad=0.0,
                speed_mps=0.0,
                bbox=(8.0, 2.4, 3.0),   # larger — represents a work truck
                spawned_t_s=t_s,
            ))
            # A few peds at the edge (work crew).
            for _ in range(3):
                self._counter += 1
                px = cx + self.rng.uniform(-10, 10)
                py = cy + self._LANE_OFFSET_M + self.rng.uniform(2, 6)
                scene.agents.append(TrafficAgent(
                    agent_id=f"ped_{self._counter:04d}",
                    cls="pedestrian",
                    x0=px, y0=py,
                    heading_rad=self.rng.uniform(0, 2 * math.pi),
                    speed_mps=self.rng.uniform(0.1, 0.6),    # crew moving slowly
                    bbox=(0.5, 0.5, 1.7),
                    spawned_t_s=t_s,
                ))
        elif scene_class == "school_zone":
            # Extra peds clustered at a single corner (a school entrance).
            corner_x = cx + self.rng.choice([-1, 1]) * 22.0
            corner_y = cy + self.rng.choice([-1, 1]) * 22.0
            for _ in range(8):
                self._counter += 1
                px = corner_x + self.rng.uniform(-4, 4)
                py = corner_y + self.rng.uniform(-4, 4)
                # Walking toward the road (crossing or queueing).
                heading = math.atan2(cy - py, cx - px) + self.rng.uniform(-0.3, 0.3)
                scene.agents.append(TrafficAgent(
                    agent_id=f"ped_{self._counter:04d}",
                    cls="pedestrian",
                    x0=px, y0=py,
                    heading_rad=heading,
                    speed_mps=self.rng.uniform(0.6, 1.4),
                    bbox=(0.4, 0.4, 1.4),
                    spawned_t_s=t_s,
                ))
        elif scene_class == "vru_interaction":
            # A cyclist on a path that will intersect a vehicle's path —
            # the kind of edge case AV training data targets.
            self._counter += 1
            scene.agents.append(TrafficAgent(
                agent_id=f"cyc_{self._counter:04d}",
                cls="cyclist",
                x0=cx - 30.0, y0=cy - 2.0,
                heading_rad=0.0,
                speed_mps=4.5,
                bbox=(1.7, 0.6, 1.6),
                spawned_t_s=t_s,
            ))
            self._counter += 1
            scene.agents.append(TrafficAgent(
                agent_id=f"veh_{self._counter:04d}",
                cls="passenger_vehicle",
                x0=cx, y0=cy - 30.0,
                heading_rad=math.pi / 2,
                speed_mps=6.0,
                bbox=(4.6, 1.8, 1.5),
                spawned_t_s=t_s,
            ))

    # -- spawning helpers ----------------------------------------------------

    # Lane geometry (relative to road centreline).
    _LANE_OFFSET_M = 3.5      # vehicles in lanes ±3.5m off centre
    _BIKE_LANE_OFFSET_M = 6.5  # bike lane 6.5m off centre
    _SIDEWALK_OFFSET_M = 11.0  # sidewalks at the road edge

    def _spawn_vehicle(self, cx: float, cy: float, t_s: float, tpl: dict) -> TrafficAgent:
        """Vehicles travel along a road axis in a lane, not jittered around it."""
        axis = self.rng.choice(tpl["road_axes"])
        speed = self.rng.uniform(*tpl["veh_speed"])
        # Direction-dependent lane offset (right-hand side of the road).
        direction = 1 if self.rng.random() < 0.5 else -1
        lane_jitter = self.rng.uniform(-0.6, 0.6)
        if axis == "ns":
            heading = math.pi / 2 if direction > 0 else -math.pi / 2
            x = cx + direction * self._LANE_OFFSET_M + lane_jitter
            y = cy + self.rng.uniform(-self.area_radius_m * 0.85,
                                       self.area_radius_m * 0.85)
        else:
            heading = 0.0 if direction > 0 else math.pi
            x = cx + self.rng.uniform(-self.area_radius_m * 0.85,
                                       self.area_radius_m * 0.85)
            y = cy + direction * self._LANE_OFFSET_M + lane_jitter
        self._counter += 1
        return TrafficAgent(
            agent_id=f"veh_{self._counter:04d}",
            cls="passenger_vehicle",
            x0=x, y0=y, heading_rad=heading, speed_mps=speed,
            bbox=(4.6, 1.8, 1.5),
            spawned_t_s=t_s,
        )

    def _spawn_pedestrian(self, cx: float, cy: float, t_s: float, tpl: dict) -> TrafficAgent:
        """Two ped patterns: crossing (perpendicular to a road) or sidewalk (along one)."""
        axes = tpl["road_axes"]
        crossing = self.rng.random() < 0.65
        speed = self.rng.uniform(0.8, 1.7)
        if crossing and "ns" in axes and "ew" in axes:
            # Walk across one of the two roads at the intersection crosswalk.
            cross_ns = self.rng.random() < 0.5
            if cross_ns:
                # Walking east-west across the N-S road, starting at one curb.
                start_dir = 1 if self.rng.random() < 0.5 else -1
                x = cx + start_dir * self._SIDEWALK_OFFSET_M
                y = cy + self.rng.uniform(-6, 6)
                heading = math.pi if start_dir > 0 else 0.0
            else:
                start_dir = 1 if self.rng.random() < 0.5 else -1
                x = cx + self.rng.uniform(-6, 6)
                y = cy + start_dir * self._SIDEWALK_OFFSET_M
                heading = -math.pi / 2 if start_dir > 0 else math.pi / 2
        elif crossing:
            # Single-road scene — peds cross the road.
            road = axes[0]
            start_dir = 1 if self.rng.random() < 0.5 else -1
            if road == "ew":
                x = cx + self.rng.uniform(-self.area_radius_m * 0.6,
                                           self.area_radius_m * 0.6)
                y = cy + start_dir * self._SIDEWALK_OFFSET_M
                heading = -math.pi / 2 if start_dir > 0 else math.pi / 2
            else:
                x = cx + start_dir * self._SIDEWALK_OFFSET_M
                y = cy + self.rng.uniform(-self.area_radius_m * 0.6,
                                           self.area_radius_m * 0.6)
                heading = math.pi if start_dir > 0 else 0.0
        else:
            # Sidewalk walker — along the road.
            road = self.rng.choice(axes)
            side = 1 if self.rng.random() < 0.5 else -1
            along_dir = 1 if self.rng.random() < 0.5 else -1
            if road == "ew":
                x = cx + self.rng.uniform(-self.area_radius_m * 0.85,
                                           self.area_radius_m * 0.85)
                y = cy + side * self._SIDEWALK_OFFSET_M
                heading = 0.0 if along_dir > 0 else math.pi
            else:
                x = cx + side * self._SIDEWALK_OFFSET_M
                y = cy + self.rng.uniform(-self.area_radius_m * 0.85,
                                           self.area_radius_m * 0.85)
                heading = math.pi / 2 if along_dir > 0 else -math.pi / 2

        self._counter += 1
        return TrafficAgent(
            agent_id=f"ped_{self._counter:04d}",
            cls="pedestrian",
            x0=x, y0=y, heading_rad=heading, speed_mps=speed,
            bbox=(0.5, 0.5, 1.7),
            spawned_t_s=t_s,
        )

    def _spawn_cyclist(self, cx: float, cy: float, t_s: float, tpl: dict) -> TrafficAgent:
        """Cyclists ride in the bike lane, parallel to the road."""
        axis = self.rng.choice(tpl["road_axes"])
        speed = self.rng.uniform(2.5, 6.0)
        direction = 1 if self.rng.random() < 0.5 else -1
        if axis == "ns":
            heading = math.pi / 2 if direction > 0 else -math.pi / 2
            x = cx + direction * self._BIKE_LANE_OFFSET_M
            y = cy + self.rng.uniform(-self.area_radius_m * 0.85,
                                       self.area_radius_m * 0.85)
        else:
            heading = 0.0 if direction > 0 else math.pi
            x = cx + self.rng.uniform(-self.area_radius_m * 0.85,
                                       self.area_radius_m * 0.85)
            y = cy + direction * self._BIKE_LANE_OFFSET_M
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
