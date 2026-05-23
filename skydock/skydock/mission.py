"""Mission state machine — orchestrates a single drone deployment lifecycle.

Maps directly to spec Section 1.1 mission profile and 9.1 stochastic hooks.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .conditions import Conditions
from .config import Config
from .drone import Drone, DroneState
from .triggers import Trigger
from .vehicle import HostVehicle


# Spec 1.1 mission stages (excluding the upload stage which is handled by the pipeline).
MISSION_STAGES = (
    "PRE_FLIGHT",
    "LAUNCHING",
    "CLIMBING",
    "CAPTURING",
    "RETURNING",
    "LANDING",
    "DONE",
    "ABORTED",
)


@dataclass
class Mission:
    mission_id: str
    started_at_s: float
    trigger: Trigger
    host_vehicle_id: str
    drone_id: str
    target_altitude_m: float
    capture_duration_s: float
    scene_class: str
    stage: str = "PRE_FLIGHT"
    stage_t_s: float = 0.0
    stage_duration_s: float = 0.0
    aborted_reason: Optional[str] = None
    completed_at_s: Optional[float] = None
    # Capture geometry — drone holds station above this point during capture.
    capture_x: float = 0.0
    capture_y: float = 0.0
    # Where the drone starts when returning (set on capture end).
    return_origin_x: float = 0.0
    return_origin_y: float = 0.0

    @property
    def is_active(self) -> bool:
        return self.stage not in ("DONE", "ABORTED")

    @property
    def is_capturing(self) -> bool:
        return self.stage == "CAPTURING"


class MissionController:
    """Drives one mission at a time. The drone is the resource; the mission is the request."""

    def __init__(self, cfg: Config, rng: random.Random):
        self.cfg = cfg
        self.rng = rng
        self._mission_counter = 0

    def start(self, trigger: Trigger, host: HostVehicle, drone: Drone, t_s: float) -> Mission:
        self._mission_counter += 1
        m_cfg = self.cfg.mission
        capture = self.rng.uniform(m_cfg.capture_seconds_min, m_cfg.capture_seconds_max)
        mission = Mission(
            mission_id=f"skydock-mission-{self._mission_counter:05d}",
            started_at_s=t_s,
            trigger=trigger,
            host_vehicle_id=host.vehicle_id,
            drone_id=drone.drone_id,
            target_altitude_m=m_cfg.target_altitude_m,
            capture_duration_s=capture,
            scene_class=trigger.waypoint.label,
            capture_x=host.x,
            capture_y=host.y,
        )
        self._enter_stage(mission, "PRE_FLIGHT", m_cfg.decision_seconds)
        drone.state = DroneState.PRE_FLIGHT
        drone.x, drone.y = host.x, host.y
        drone.altitude_m = 0.0
        return mission

    # -- per-tick step ------------------------------------------------------

    def step(
        self,
        mission: Mission,
        drone: Drone,
        host: HostVehicle,
        conditions: Conditions,
        dt: float,
        t_s: float,
    ) -> None:
        mission.stage_t_s += dt
        stage_done = mission.stage_t_s >= mission.stage_duration_s

        if mission.stage == "PRE_FLIGHT":
            drone.x, drone.y = host.x, host.y
            drone.altitude_m = 0.0
            if stage_done:
                if self._pass_pre_flight(conditions, drone):
                    self._enter_stage(mission, "LAUNCHING", self.cfg.mission.launch_seconds)
                    drone.state = DroneState.LAUNCHING
                else:
                    self._abort(mission, drone, reason=self._pre_flight_reason(conditions, drone))

        elif mission.stage == "LAUNCHING":
            drone.x, drone.y = host.x, host.y
            drone.altitude_m = 5.0 * (mission.stage_t_s / mission.stage_duration_s)
            if stage_done:
                if self.rng.random() < self.cfg.probabilities.launch_success:
                    self._enter_stage(mission, "CLIMBING", self.cfg.mission.climb_seconds)
                    drone.state = DroneState.CLIMBING
                else:
                    self._abort(mission, drone, reason="launch_mechanical")

        elif mission.stage == "CLIMBING":
            drone.x, drone.y = mission.capture_x, mission.capture_y
            progress = min(1.0, mission.stage_t_s / mission.stage_duration_s)
            drone.altitude_m = 5.0 + progress * (mission.target_altitude_m - 5.0)
            if stage_done:
                self._enter_stage(mission, "CAPTURING", mission.capture_duration_s)
                drone.state = DroneState.CAPTURING

        elif mission.stage == "CAPTURING":
            drone.x, drone.y = mission.capture_x, mission.capture_y
            drone.altitude_m = mission.target_altitude_m
            if stage_done:
                mission.return_origin_x = drone.x
                mission.return_origin_y = drone.y
                self._enter_stage(mission, "RETURNING", self.cfg.mission.return_seconds)
                drone.state = DroneState.RETURNING

        elif mission.stage == "RETURNING":
            progress = min(1.0, mission.stage_t_s / mission.stage_duration_s)
            drone.x = mission.return_origin_x + (host.x - mission.return_origin_x) * progress
            drone.y = mission.return_origin_y + (host.y - mission.return_origin_y) * progress
            drone.altitude_m = mission.target_altitude_m
            if stage_done:
                self._enter_stage(mission, "LANDING", self.cfg.mission.land_seconds)
                drone.state = DroneState.LANDING

        elif mission.stage == "LANDING":
            drone.x, drone.y = host.x, host.y
            progress = min(1.0, mission.stage_t_s / mission.stage_duration_s)
            drone.altitude_m = mission.target_altitude_m * (1.0 - progress)
            if stage_done:
                if self.rng.random() < self.cfg.probabilities.recovery_success:
                    self._enter_stage(mission, "DONE", 0.0)
                    drone.state = DroneState.DOCKED
                    drone.altitude_m = 0.0
                    mission.completed_at_s = t_s
                else:
                    self._abort(mission, drone, reason="dock_latch_fail")

    # -- helpers ------------------------------------------------------------

    def _enter_stage(self, mission: Mission, stage: str, duration_s: float) -> None:
        mission.stage = stage
        mission.stage_t_s = 0.0
        mission.stage_duration_s = duration_s

    def _abort(self, mission: Mission, drone: Drone, reason: str) -> None:
        mission.aborted_reason = reason
        self._enter_stage(mission, "ABORTED", 0.0)
        # Drone is always recoverable to dock in v0 — alternative would be LOST.
        drone.state = DroneState.DOCKED
        drone.altitude_m = 0.0

    def _pass_pre_flight(self, c: Conditions, drone: Drone) -> bool:
        # Hard gates from spec 1.4.
        if c.wind_mph >= self.cfg.conditions.wind_abort_threshold_mph:
            return False
        if not c.weather_clear:
            return False
        if drone.battery_pct < 40.0:
            return False
        return self.rng.random() < self.cfg.probabilities.pre_flight_pass

    def _pre_flight_reason(self, c: Conditions, drone: Drone) -> str:
        if c.wind_mph >= self.cfg.conditions.wind_abort_threshold_mph:
            return "wind_too_high"
        if not c.weather_clear:
            return "weather"
        if drone.battery_pct < 40.0:
            return "low_battery"
        return "pre_flight_check"
