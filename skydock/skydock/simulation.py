"""Top-level simulation orchestrator wiring all subsystems."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .conditions import Conditions, ConditionsModel
from .config import Config
from .drone import Drone, DroneState
from .economics import Economics
from .metrics import Metrics
from .mission import Mission, MissionController
from .pipeline import DataPipeline, PipelineJob
from .triggers import Trigger, TriggerGenerator
from .vehicle import HostVehicle
from .world import Waypoint, generate_corridor


@dataclass
class SimSnapshot:
    """Read-only view of sim state used by the animation."""
    t_s: float
    conditions: Conditions
    vehicle: HostVehicle
    drone: Drone
    waypoints: list[Waypoint]
    active_mission: Optional[Mission]
    metrics: Metrics
    economics: Economics
    pipeline: DataPipeline


class Simulation:
    def __init__(self, config: Config):
        self.cfg = config
        self.rng = random.Random(config.simulation.seed)
        self.t_s: float = 0.0
        self.duration_s: float = config.simulation.duration_hours * 3600.0

        self.waypoints = generate_corridor(
            width_m=config.world.width_m,
            height_m=config.world.height_m,
            n_waypoints=10,
            rng=self.rng,
        )
        speed_mps = config.host_vehicles.speed_mph_cruise / 2.23694
        self.vehicle = HostVehicle(
            vehicle_id="host_0",
            waypoints=self.waypoints,
            speed_mps=speed_mps,
        )
        self.drone = Drone(drone_id="drone_0", x=self.vehicle.x, y=self.vehicle.y)

        self.conditions_model = ConditionsModel(
            config.conditions, config.world, config.simulation, self.rng,
        )
        self.trigger_gen = TriggerGenerator(config.trigger, self.waypoints, self.rng)
        self.mission_ctrl = MissionController(config, self.rng)
        self.pipeline = DataPipeline(config.pipeline, config.probabilities, self.rng)
        self.economics = Economics(config.economics, host_vehicle_count=1)
        self.metrics = Metrics()

        self.active_mission: Optional[Mission] = None
        self.completed_missions: list[Mission] = []
        self.completed_jobs: list[PipelineJob] = []

    # -- core loop ----------------------------------------------------------

    def step(self, dt: float | None = None) -> SimSnapshot:
        dt = dt or self.cfg.simulation.dt_seconds
        cond = self.conditions_model.current(self.t_s)
        operating = cond.is_daylight

        if operating:
            reached_wp = self.vehicle.update(dt)
        else:
            reached_wp = None

        # When the vehicle arrives at a waypoint, briefly stop — gives a chance
        # for waypoint-trigger to fire (spec 1.3 pre-planned trigger).
        if reached_wp is not None and operating:
            self.vehicle.stop_for(self.cfg.host_vehicles.stop_at_waypoint_seconds)
            if self.drone.state == DroneState.DOCKED and self.active_mission is None:
                trig = self.trigger_gen.trigger_on_waypoint(self.t_s, self.vehicle, reached_wp)
                if trig is not None:
                    self._begin_mission(trig)

        # Poisson trigger source — only while operating and drone is free.
        if (
            operating
            and self.active_mission is None
            and self.drone.state == DroneState.DOCKED
        ):
            trig = self.trigger_gen.poll(dt, self.t_s, self.vehicle)
            if trig is not None:
                self._begin_mission(trig)
        elif operating and self.trigger_gen.poll(dt, self.t_s, self.vehicle):
            # Trigger arrived but drone busy / outside envelope — count it as skipped.
            self.metrics.triggers_skipped_drone_busy += 1

        # Step the active mission (also moves the drone).
        if self.active_mission is not None:
            self.mission_ctrl.step(
                self.active_mission, self.drone, self.vehicle, cond, dt, self.t_s,
            )
            if not self.active_mission.is_active:
                self._finalize_mission(self.active_mission)
                self.active_mission = None
        else:
            # Idle — drone sits on host vehicle.
            self.drone.x, self.drone.y = self.vehicle.x, self.vehicle.y
            self.drone.altitude_m = 0.0

        self.drone.charge_or_drain(dt)

        for job in self.pipeline.step(self.t_s):
            self._finalize_pipeline_job(job)

        self.economics.tick(dt, operating=operating)
        self.t_s += dt

        return self.snapshot(cond)

    def run_headless(self) -> None:
        while self.t_s < self.duration_s:
            self.step()

    def snapshot(self, cond: Conditions | None = None) -> SimSnapshot:
        cond = cond or self.conditions_model.current(self.t_s)
        return SimSnapshot(
            t_s=self.t_s,
            conditions=cond,
            vehicle=self.vehicle,
            drone=self.drone,
            waypoints=self.waypoints,
            active_mission=self.active_mission,
            metrics=self.metrics,
            economics=self.economics,
            pipeline=self.pipeline,
        )

    # -- internals ----------------------------------------------------------

    def _begin_mission(self, trigger: Trigger) -> None:
        # If the host is moving fast (>5 mph spec 1.4), abort before launch.
        if self.vehicle.speed_mph > 5.0 and not self.vehicle.stopped:
            self.metrics.triggers_skipped_outside_envelope += 1
            return
        self.active_mission = self.mission_ctrl.start(
            trigger, self.vehicle, self.drone, self.t_s,
        )
        self.metrics.on_mission_start(trigger.type)

    def _finalize_mission(self, mission: Mission) -> None:
        self.completed_missions.append(mission)
        if mission.stage == "DONE":
            self.metrics.on_mission_success(mission.scene_class)
            self.pipeline.enqueue(mission, self.t_s)
        else:
            reason = mission.aborted_reason or "unknown"
            self.metrics.on_mission_abort(reason)

    def _finalize_pipeline_job(self, job: PipelineJob) -> None:
        self.completed_jobs.append(job)
        if job.delivered:
            self.metrics.on_delivery(job.quality_score)
            self.economics.record_delivery()
