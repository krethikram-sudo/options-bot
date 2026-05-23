"""Mission state machine — orchestrates a single drone deployment lifecycle.

Stage transitions are physics-driven (with timeout fallbacks) instead of
hardcoded durations: CLIMBING ends when the drone reaches target altitude,
RETURNING ends when the drone is over the dock, LANDING ends when the
drone touches down. The dock model decides whether the latch caught.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .conditions import Conditions
from .config import Config
from .dock import latch_success_probability
from .drone import Drone, DroneState
from .triggers import Trigger
from .vehicle import HostVehicle


# Spec §1.1 stages (DONE / ABORTED are terminal).
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
    stage_timeout_s: float = 0.0       # safety upper bound on the stage
    aborted_reason: Optional[str] = None
    completed_at_s: Optional[float] = None
    # Capture geometry — drone holds station above this point during capture.
    capture_x: float = 0.0
    capture_y: float = 0.0
    # Failure cascade outcomes (spec §7.1) — consumed by the Simulation.
    drone_lost: bool = False
    dock_damaged: bool = False
    # Battery-aware RTL: mission cut short to return to dock before depletion.
    early_rtl_battery: bool = False
    # Capture quality from observed scene; set when CAPTURING ends.
    quality_score_from_scene: Optional[float] = None

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
        drone.physics.snap_to(host.x, host.y, 0.0)
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
        wind_dir = 0.0   # constant wind direction for v0 — east-bound

        # Battery-aware RTL — if the drone is airborne and battery dipped below
        # the safe-return threshold, cut the capture short and return to dock.
        # Below the crash threshold, the drone is LOST mid-flight.
        if drone.is_airborne:
            if drone.battery_pct <= self.cfg.mission.crash_battery_threshold_pct:
                mission.drone_lost = True
                mission.aborted_reason = "drone_lost_low_battery"
                self._enter_stage(mission, "ABORTED", 0.0)
                drone.state = DroneState.LOST
                drone.altitude_m = 0.0
                return
            if (drone.battery_pct <= self.cfg.mission.rtl_battery_threshold_pct
                    and mission.stage in ("CLIMBING", "CAPTURING")):
                mission.early_rtl_battery = True
                # End the current stage and start the descent home immediately.
                self._enter_stage(mission, "RETURNING",
                                   self.cfg.mission.return_seconds * 3)
                drone.state = DroneState.RETURNING

        if mission.stage == "PRE_FLIGHT":
            # Drone parked on dock — physics body just sits at host position.
            drone.physics.snap_to(host.x, host.y, 0.0)
            if mission.stage_t_s >= mission.stage_timeout_s:
                if self._pass_pre_flight(conditions, drone):
                    self._enter_stage(mission, "LAUNCHING",
                                       self.cfg.mission.launch_seconds * 2)
                    drone.state = DroneState.LAUNCHING
                    drone.physics.target_x = host.x
                    drone.physics.target_y = host.y
                    drone.physics.target_z = 5.0   # clear the dock
                else:
                    self._abort(mission, drone,
                                reason=self._pre_flight_reason(conditions, drone))

        elif mission.stage == "LAUNCHING":
            drone.physics.step(dt, conditions.wind_mph, wind_dir)
            # Stage ends when drone has cleared the dock (z > 3m).
            if drone.altitude_m > 3.0:
                if self.rng.random() < self.cfg.probabilities.launch_success:
                    self._enter_stage(mission, "CLIMBING",
                                       self.cfg.mission.climb_seconds * 3)
                    drone.state = DroneState.CLIMBING
                    drone.physics.target_x = mission.capture_x
                    drone.physics.target_y = mission.capture_y
                    drone.physics.target_z = mission.target_altitude_m
                else:
                    self._abort(mission, drone, reason="launch_mechanical")
            elif mission.stage_t_s > mission.stage_timeout_s:
                self._abort(mission, drone, reason="launch_mechanical")

        elif mission.stage == "CLIMBING":
            drone.physics.target_x = mission.capture_x
            drone.physics.target_y = mission.capture_y
            drone.physics.target_z = mission.target_altitude_m
            drone.physics.step(dt, conditions.wind_mph, wind_dir)
            if drone.physics.at_target(horizontal_tol_m=3.0, vertical_tol_m=1.5):
                self._enter_stage(mission, "CAPTURING", mission.capture_duration_s)
                drone.state = DroneState.CAPTURING
            elif mission.stage_t_s > mission.stage_timeout_s:
                # Couldn't reach altitude in time — probably wind or low battery.
                self._abort(mission, drone, reason="climb_timeout")

        elif mission.stage == "CAPTURING":
            # Hold station above capture point.
            drone.physics.target_x = mission.capture_x
            drone.physics.target_y = mission.capture_y
            drone.physics.target_z = mission.target_altitude_m
            drone.physics.step(dt, conditions.wind_mph, wind_dir)
            if mission.stage_t_s >= mission.capture_duration_s:
                self._enter_stage(mission, "RETURNING",
                                   self.cfg.mission.return_seconds * 3)
                drone.state = DroneState.RETURNING

        elif mission.stage == "RETURNING":
            drone.physics.target_x = host.x
            drone.physics.target_y = host.y
            drone.physics.target_z = mission.target_altitude_m
            drone.physics.step(dt, conditions.wind_mph, wind_dir)
            # Done when horizontally close to the dock.
            dx = drone.physics.x - host.x
            dy = drone.physics.y - host.y
            if (dx * dx + dy * dy) ** 0.5 < 3.0:
                self._enter_stage(mission, "LANDING",
                                   self.cfg.mission.land_seconds * 3)
                drone.state = DroneState.LANDING
            elif mission.stage_t_s > mission.stage_timeout_s:
                self._abort(mission, drone, reason="return_timeout")

        elif mission.stage == "LANDING":
            drone.physics.target_x = host.x
            drone.physics.target_y = host.y
            drone.physics.target_z = 0.0
            drone.physics.step(dt, conditions.wind_mph, wind_dir)
            if drone.altitude_m < 0.5:
                self._resolve_landing(mission, drone, host, conditions, t_s)
            elif mission.stage_t_s > mission.stage_timeout_s:
                self._abort(mission, drone, reason="landing_timeout")

    # -- helpers ------------------------------------------------------------

    def _enter_stage(self, mission: Mission, stage: str, timeout_s: float) -> None:
        mission.stage = stage
        mission.stage_t_s = 0.0
        mission.stage_timeout_s = timeout_s

    def _abort(self, mission: Mission, drone: Drone, reason: str) -> None:
        mission.aborted_reason = reason
        self._enter_stage(mission, "ABORTED", 0.0)
        drone.state = DroneState.DOCKED
        drone.altitude_m = 0.0

    def _resolve_landing(
        self,
        mission: Mission,
        drone: Drone,
        host: HostVehicle,
        conditions: Conditions,
        t_s: float,
    ) -> None:
        """Final landing — dock physics + failure-cascade rolls."""
        cascades = self.cfg.failure_cascades

        # 1. Flyaway during flight → drone LOST.
        if (cascades.enabled
                and self.rng.random() < cascades.drone_flyaway_prob_per_mission):
            mission.drone_lost = True
            mission.aborted_reason = "drone_lost"
            self._enter_stage(mission, "ABORTED", 0.0)
            drone.state = DroneState.LOST
            drone.altitude_m = 0.0
            return

        # 2. Dock latch — geometry + conditions, not a flat coin flip.
        p_latch = latch_success_probability(
            self.cfg.dock,
            drone_x=drone.physics.x, drone_y=drone.physics.y,
            drone_vz=drone.physics.vz,
            dock_x=host.x, dock_y=host.y,
            vehicle_speed_mph=host.speed_mph,
            wind_mph=conditions.wind_mph,
            base_recovery_prob=self.cfg.probabilities.recovery_success,
        )
        if self.rng.random() >= p_latch:
            self._abort(mission, drone, reason="dock_latch_fail")
            return

        # 3. Success.
        self._enter_stage(mission, "DONE", 0.0)
        drone.state = DroneState.DOCKED
        drone.physics.snap_to(host.x, host.y, 0.0)
        mission.completed_at_s = t_s
        drone.register_flight_complete(cascades.battery_degradation_per_flight_pct
                                       if cascades.enabled else 0.0)

        if (cascades.enabled
                and self.rng.random() < cascades.dock_damage_prob_per_landing):
            mission.dock_damaged = True

    def _pass_pre_flight(self, c: Conditions, drone: Drone) -> bool:
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
