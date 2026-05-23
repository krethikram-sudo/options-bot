"""Emit per-scenario deliverable packages (spec 3.2/3.3/3.4).

Each delivered scenario produces a directory:

    out/scenarios/{scenario_id}/
        metadata.json
        agent_tracks.json
        scenario.xosc     (minimal OpenSCENARIO 2 stub)

The agent tracks are synthesised — not from real video — but the shapes
match what a customer would receive from the real pipeline, so the
package looks like the real deliverable.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .mission import Mission


# Anchor lat/lon for synthetic geolocation — Mountain View, per spec 3.3 example.
_ANCHOR_LAT = 37.4234
_ANCHOR_LON = -122.0832


def emit_scenario_package(
    mission: Mission,
    quality_score: float,
    out_dir: Path | str,
    rng: random.Random,
    wall_clock_start: datetime | None = None,
) -> Path:
    out = Path(out_dir) / mission.mission_id
    out.mkdir(parents=True, exist_ok=True)

    captured_at = (wall_clock_start or datetime.now(timezone.utc)) + timedelta(
        seconds=mission.started_at_s
    )

    agents = _synthesize_agents(mission, rng)
    tracks_payload = _build_tracks_payload(mission, agents, captured_at)
    metadata = _build_metadata(mission, quality_score, captured_at, agents)

    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (out / "agent_tracks.json").write_text(json.dumps(tracks_payload, indent=2))
    (out / "scenario.xosc").write_text(_build_openscenario_stub(mission, captured_at, agents))
    return out


# -- metadata.json (spec 3.3) -------------------------------------------

def _build_metadata(
    mission: Mission,
    quality_score: float,
    captured_at: datetime,
    agents: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = {"passenger_vehicle": 0, "pedestrian": 0, "cyclist": 0, "other": 0}
    for a in agents:
        counts[a["class"]] = counts.get(a["class"], 0) + 1

    return {
        "scenario_id": mission.mission_id,
        "captured_at": captured_at.isoformat(),
        "duration_seconds": round(mission.capture_duration_s, 2),
        "location": {
            "lat": _ANCHOR_LAT + (mission.capture_x - 2500.0) / 111_000.0,
            "lon": _ANCHOR_LON + (mission.capture_y - 2500.0) / 111_000.0,
            "address": f"synthetic — {mission.scene_class}",
            "approximate": True,
        },
        "weather": {
            "conditions": "clear",
            "temperature_c": 22,
            "wind_speed_mph": 8,
        },
        "trigger": {
            "type": mission.trigger.type,
            "operator_note": f"{mission.trigger.type} trigger at {mission.scene_class}",
        },
        "scene_classification": {
            "primary": mission.scene_class,
            "secondary": _secondary_modifiers(mission.scene_class),
        },
        "agent_summary": {
            "vehicles": counts.get("passenger_vehicle", 0),
            "pedestrians": counts.get("pedestrian", 0),
            "cyclists": counts.get("cyclist", 0),
            "other": counts.get("other", 0),
        },
        "quality_score": round(quality_score, 1),
    }


def _secondary_modifiers(primary: str) -> list[str]:
    table = {
        "intersection_signalized": ["pedestrian_crosswalk"],
        "intersection_unsignalized": ["high_pedestrian_density"],
        "unprotected_left_turn": ["pedestrian_crosswalk", "high_pedestrian_density"],
        "school_zone": ["high_pedestrian_density"],
        "pedestrian_crosswalk": ["high_pedestrian_density"],
        "construction_zone": ["obstacle_in_road"],
        "vru_interaction": ["cyclist_present"],
        "merge_highway": ["large_vehicle_present"],
        "merge_arterial": ["cyclist_present"],
        "lane_change_complex": [],
    }
    return table.get(primary, [])


# -- agent_tracks.json (spec 3.4) ---------------------------------------

def _synthesize_agents(mission: Mission, rng: random.Random) -> list[dict[str, Any]]:
    """Generate plausible agents within the drone footprint with straight-line motion."""
    density = {
        "intersection_signalized": (10, 14, 3),
        "intersection_unsignalized": (6, 8, 1),
        "unprotected_left_turn": (8, 18, 2),
        "school_zone": (4, 22, 1),
        "pedestrian_crosswalk": (3, 16, 2),
        "construction_zone": (5, 4, 1),
        "merge_arterial": (12, 2, 2),
        "merge_highway": (16, 0, 0),
        "lane_change_complex": (10, 1, 1),
        "vru_interaction": (5, 8, 4),
    }.get(mission.scene_class, (6, 6, 1))
    n_veh, n_ped, n_cyc = density

    agents: list[dict[str, Any]] = []
    radius_m = 110.0
    for i in range(n_veh):
        agents.append(_make_agent("passenger_vehicle", f"veh_{i:03d}", radius_m, rng,
                                  speed_range=(2.0, 12.0), bbox=(4.6, 1.8, 1.5)))
    for i in range(n_ped):
        agents.append(_make_agent("pedestrian", f"ped_{i:03d}", radius_m, rng,
                                  speed_range=(0.8, 1.8), bbox=(0.5, 0.5, 1.7)))
    for i in range(n_cyc):
        agents.append(_make_agent("cyclist", f"cyc_{i:03d}", radius_m, rng,
                                  speed_range=(2.5, 6.0), bbox=(1.7, 0.6, 1.6)))
    return agents


def _make_agent(
    cls: str,
    track_id: str,
    radius_m: float,
    rng: random.Random,
    speed_range: tuple[float, float],
    bbox: tuple[float, float, float],
) -> dict[str, Any]:
    angle = rng.uniform(0, 2 * math.pi)
    r = rng.uniform(0, radius_m * 0.9)
    x0 = math.cos(angle) * r
    y0 = math.sin(angle) * r
    heading = rng.uniform(0, 2 * math.pi)
    speed = rng.uniform(*speed_range)
    return {
        "track_id": track_id,
        "class": cls,
        "x0": x0,
        "y0": y0,
        "heading_rad": heading,
        "speed_mps": speed,
        "bbox": bbox,
    }


def _build_tracks_payload(
    mission: Mission,
    agents: list[dict[str, Any]],
    captured_at: datetime,
) -> dict[str, Any]:
    fps = 30
    n_frames = int(mission.capture_duration_s * fps)
    serialized = []
    for a in agents:
        frames = []
        # Limit to 90 frames per agent in JSON to keep file sizes reasonable.
        sample_step = max(1, n_frames // 90)
        for f in range(0, n_frames, sample_step):
            t = f / fps
            x = a["x0"] + math.cos(a["heading_rad"]) * a["speed_mps"] * t
            y = a["y0"] + math.sin(a["heading_rad"]) * a["speed_mps"] * t
            frames.append({
                "f": f,
                "x": round(x, 2),
                "y": round(y, 2),
                "heading_deg": round(math.degrees(a["heading_rad"]) % 360, 1),
                "speed_mps": round(a["speed_mps"], 2),
            })
        serialized.append({
            "track_id": a["track_id"],
            "class": a["class"],
            "first_frame": 0,
            "last_frame": n_frames - 1,
            "bounding_box_dimensions_m": list(a["bbox"]),
            "frames": frames,
        })
    return {
        "scenario_id": mission.mission_id,
        "timestamp_origin": captured_at.isoformat(),
        "frame_rate_hz": fps,
        "duration_frames": n_frames,
        "coordinate_system": "local ENU frame anchored at capture point",
        "agents": serialized,
    }


# -- scenario.xosc (OpenSCENARIO 2 stub) --------------------------------

def _build_openscenario_stub(
    mission: Mission,
    captured_at: datetime,
    agents: list[dict[str, Any]],
) -> str:
    """A minimal OpenSCENARIO XML stub. Not a complete spec doc — enough to demo the format."""
    entities = []
    for a in agents[:20]:  # cap the stub at first 20 agents
        entities.append(
            f'    <ScenarioObject name="{a["track_id"]}">\n'
            f'      <{"Vehicle" if a["class"] == "passenger_vehicle" else "Pedestrian"} '
            f'name="{a["class"]}"/>\n'
            f'    </ScenarioObject>'
        )
    entities_xml = "\n".join(entities)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<OpenSCENARIO>\n'
        '  <FileHeader '
        f'revMajor="1" revMinor="2" '
        f'date="{captured_at.isoformat()}" '
        f'description="skydock {mission.scene_class} synthetic stub" '
        f'author="skydock-sim"/>\n'
        '  <Entities>\n'
        f'{entities_xml}\n'
        '  </Entities>\n'
        '  <Storyboard>\n'
        f'    <!-- {mission.capture_duration_s:.1f} second capture; '
        f'{len(agents)} agents tracked -->\n'
        '  </Storyboard>\n'
        '</OpenSCENARIO>\n'
    )
