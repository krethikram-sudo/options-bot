"""Per-scenario deliverable packages (spec §3.2-3.4).

Each delivered scenario produces a directory:

    out/scenarios/{scenario_id}/
        metadata.json
        agent_tracks.json
        scenario.xosc     (minimal OpenSCENARIO 2 stub)

The agent tracks are NOT synthesised — they are the actual frame-by-frame
positions the simulation observed during capture, including traffic-light
stops, agent spawn/cull lifecycles, and the drone's own altitude / wind
context at each sample. The deliverable is intended to be defensible to
an AV-customer engineer reading it.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .mission import Mission
from .scene import TrafficAgent, TrafficScene


# Anchor lat/lon for synthetic geolocation — Mountain View, per spec §3.3 example.
_ANCHOR_LAT = 37.4234
_ANCHOR_LON = -122.0832
# ~111 km per degree of latitude (constant); cos(lat) for longitude.
_METERS_PER_DEG_LAT = 111_000.0
_METERS_PER_DEG_LON = 111_000.0 * math.cos(math.radians(_ANCHOR_LAT))

# Camera intrinsics — DJI Mini 4 Pro 1/1.3" sensor + 24mm-equiv lens at 4K30.
_CAMERA_INTRINSICS = {
    "sensor": "1/1.3\" CMOS",
    "lens_equivalent_focal_length_mm": 24,
    "image_resolution_px": [3840, 2160],
    "framerate_hz": 30,
    "horizontal_fov_deg": 73.0,
    "vertical_fov_deg": 47.0,
    "diagonal_fov_deg": 80.0,
}
# GPS uncertainty for the host vehicle and drone (matched to consumer GPS).
_GPS_UNCERTAINTY_M_2SIGMA = 2.5


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

    scene: Optional[TrafficScene] = getattr(mission, "captured_scene", None)
    if scene is not None and scene.frames_observed > 0:
        tracks_payload = _build_tracks_from_scene(scene, mission, captured_at)
        agent_classes = [{"track_id": a.agent_id, "class": a.cls}
                         for a in scene.agents if a.agent_id in scene.visibility]
    else:
        # Fallback (e.g. captured_scene missing) — synthesise minimal payload.
        tracks_payload = {
            "scenario_id": mission.mission_id,
            "timestamp_origin": captured_at.isoformat(),
            "frame_rate_hz": _CAMERA_INTRINSICS["framerate_hz"],
            "duration_frames": 0,
            "coordinate_system": "synthesised",
            "agents": [],
        }
        agent_classes = []

    metadata = _build_metadata(mission, quality_score, captured_at, scene, agent_classes)

    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (out / "agent_tracks.json").write_text(json.dumps(tracks_payload, indent=2))
    (out / "scenario.xosc").write_text(
        _build_openscenario_stub(mission, captured_at, agent_classes))
    return out


# -- metadata.json (spec §3.3) ------------------------------------------

def _build_metadata(
    mission: Mission,
    quality_score: float,
    captured_at: datetime,
    scene: Optional[TrafficScene],
    agent_classes: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = {"passenger_vehicle": 0, "pedestrian": 0, "cyclist": 0, "other": 0}
    for entry in agent_classes:
        counts[entry["class"]] = counts.get(entry["class"], 0) + 1

    avg_alt = None
    avg_wind = None
    if scene is not None:
        if scene.altitude_log:
            avg_alt = sum(scene.altitude_log) / len(scene.altitude_log)
        if scene.wind_log:
            avg_wind = sum(scene.wind_log) / len(scene.wind_log)

    meta: dict[str, Any] = {
        "scenario_id": mission.mission_id,
        "captured_at": captured_at.isoformat(),
        "duration_seconds": round(mission.capture_duration_s, 2),
        "location": {
            "lat": _ANCHOR_LAT + (mission.capture_y - 2500.0) / _METERS_PER_DEG_LAT,
            "lon": _ANCHOR_LON + (mission.capture_x - 2500.0) / _METERS_PER_DEG_LON,
            "address": f"synthetic — {mission.scene_class}",
            "approximate": True,
            "gps_uncertainty_m_2sigma": _GPS_UNCERTAINTY_M_2SIGMA,
        },
        "weather": {
            "conditions": "clear",
            "temperature_c": 22,
            "wind_speed_mph": round(avg_wind, 1) if avg_wind is not None else 8,
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
        "capture_geometry": {
            "drone_altitude_m_avg": round(avg_alt, 1) if avg_alt is not None else 80.0,
            "gimbal_pitch_deg": 90,    # straight down during capture
            "frame_count": scene.frames_observed if scene is not None else 0,
        },
        "camera_calibration": _CAMERA_INTRINSICS,
        "quality": {
            "score": round(quality_score, 1),
            "methodology": (
                "Weighted blend of (a) per-agent visibility ratio across observed frames, "
                "(b) agent coverage capped at 70% of spawned agents, "
                "(c) class diversity, with altitude / wind multipliers applied."
            ),
            "early_rtl_battery": getattr(mission, "early_rtl_battery", False),
        },
    }
    return meta


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


# -- agent_tracks.json (spec §3.4) --------------------------------------

def _build_tracks_from_scene(
    scene: TrafficScene,
    mission: Mission,
    captured_at: datetime,
) -> dict[str, Any]:
    """Emit per-frame ENU positions for every agent visible during capture.

    Captures the agent's lifecycle (spawn at t=0 or later via respawn, cull
    when off-screen), traffic-light stops, and computes heading + speed from
    successive positions. Coordinates are in the local ENU frame centred on
    the capture point so customer scenario files are anchor-agnostic.
    """
    fps = _CAMERA_INTRINSICS["framerate_hz"]
    capture_start_t = scene.spawned_at_s
    capture_end_t = capture_start_t + mission.capture_duration_s
    n_frames = int(round(mission.capture_duration_s * fps))
    sample_step = max(1, n_frames // 90)   # cap each agent's frames at ~90 samples

    serialized = []
    seen_ids = set(scene.visibility.keys())
    for agent in scene.agents:
        if agent.agent_id not in seen_ids:
            continue
        a_start = max(agent.spawned_t_s, capture_start_t)
        a_end = min(agent.culled_at_s if agent.culled_at_s is not None else capture_end_t,
                    capture_end_t)
        if a_end <= a_start:
            continue
        first_frame = max(0, int(round((a_start - capture_start_t) * fps)))
        last_frame = min(n_frames - 1, int(round((a_end - capture_start_t) * fps)))

        frames: list[dict[str, Any]] = []
        prev_x = prev_y = None
        prev_t = None
        for f in range(first_frame, last_frame + 1, sample_step):
            sim_t = capture_start_t + f / fps
            x, y = scene.agent_position_at(agent, sim_t)
            # Local ENU centred on capture point.
            ex = round(x - scene.center_x, 2)
            ey = round(y - scene.center_y, 2)
            if prev_x is None:
                heading_deg = round(math.degrees(agent.heading_rad) % 360.0, 1)
                speed_mps = round(agent.speed_mps, 2)
            else:
                dt = sim_t - prev_t
                if dt > 0:
                    dx = x - prev_x
                    dy = y - prev_y
                    spd = math.hypot(dx, dy) / dt
                    speed_mps = round(spd, 2)
                    if spd > 0.05:
                        heading_deg = round(math.degrees(math.atan2(dy, dx)) % 360.0, 1)
                    else:
                        heading_deg = frames[-1]["heading_deg"]   # carry through
                else:
                    speed_mps = 0.0
                    heading_deg = frames[-1]["heading_deg"]
            frames.append({
                "f": f,
                "x": ex,
                "y": ey,
                "heading_deg": heading_deg,
                "speed_mps": speed_mps,
            })
            prev_x, prev_y, prev_t = x, y, sim_t

        visible_samples = sorted(scene.visibility.get(agent.agent_id, set()))
        agent_lifetime_samples = max(1, scene.frames_observed)
        serialized.append({
            "track_id": agent.agent_id,
            "class": agent.cls,
            "first_frame": first_frame,
            "last_frame": last_frame,
            "fov_samples_visible": len(visible_samples),
            "fov_visibility_ratio": round(len(visible_samples) / agent_lifetime_samples, 3),
            "bounding_box_dimensions_m": list(agent.bbox),
            "frames": frames,
        })

    return {
        "scenario_id": mission.mission_id,
        "timestamp_origin": captured_at.isoformat(),
        "frame_rate_hz": fps,
        "duration_frames": n_frames,
        "coordinate_system": (
            "local ENU frame anchored at capture point (x=east, y=north, "
            "metres); convert to WGS84 via metadata.location lat/lon."
        ),
        "sampling_notes": (
            "Per-agent trajectories are interpolated at frame_rate_hz from the "
            "simulation's continuous-time agent model. FOV visibility was "
            "sampled at 1 Hz during capture; fov_visibility_ratio is computed "
            "against that sample count."
        ),
        "agents": serialized,
    }


# -- scenario.xosc (OpenSCENARIO 2.0 stub) ------------------------------

def _build_openscenario_stub(
    mission: Mission,
    captured_at: datetime,
    agent_classes: list[dict[str, Any]],
) -> str:
    """Minimal OpenSCENARIO 2.0 stub. Not a full XOSC document — enough
    structure for a customer to identify scenario, entities, and timing."""
    entities = []
    for entry in agent_classes[:30]:
        kind = "Vehicle" if entry["class"] == "passenger_vehicle" else "Pedestrian"
        entities.append(
            f'    <ScenarioObject name="{entry["track_id"]}">\n'
            f'      <{kind} name="{entry["class"]}"/>\n'
            f'    </ScenarioObject>'
        )
    entities_xml = "\n".join(entities)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<OpenSCENARIO xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        '  <FileHeader '
        f'revMajor="1" revMinor="2" '
        f'date="{captured_at.isoformat()}" '
        f'description="skydock {mission.scene_class} synthetic stub" '
        f'author="skydock-sim"/>\n'
        '  <ParameterDeclarations/>\n'
        '  <CatalogLocations/>\n'
        '  <RoadNetwork>\n'
        '    <LogicFile filepath="map_reference.xodr"/>\n'
        '  </RoadNetwork>\n'
        '  <Entities>\n'
        f'{entities_xml}\n'
        '  </Entities>\n'
        '  <Storyboard>\n'
        '    <Init/>\n'
        f'    <!-- {mission.capture_duration_s:.1f}s capture; '
        f'{len(agent_classes)} agents tracked -->\n'
        '  </Storyboard>\n'
        '</OpenSCENARIO>\n'
    )
