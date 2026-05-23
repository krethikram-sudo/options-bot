"""Top-level simulation orchestrator wiring all subsystems."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
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
class VehicleUnit:
    """One host vehicle + its drone + the trigger generator that schedules its missions."""
    vehicle: HostVehicle
    drone: Drone
    trigger_gen: TriggerGenerator
    active_mission: Optional[Mission] = None
    color: str = "#9ee37d"


@dataclass
class SimSnapshot:
    """Read-only view of sim state used by the animation."""
    t_s: float
    conditions: Conditions
    units: list[VehicleUnit]
    waypoints: list[Waypoint]
    metrics: Metrics
    economics: Economics
    pipeline: DataPipeline


# Colour palette for up to 8 host vehicles in the same animation.
_VEHICLE_COLORS = [
    "#9ee37d", "#7ab0d4", "#f29ac4", "#e5b85a",
    "#c39bd3", "#76d7c4", "#f1948a", "#aab7b8",
]


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
        n = max(1, int(config.host_vehicles.count))

        self.units: list[VehicleUnit] = []
        for i in range(n):
            # Offset each vehicle's start waypoint so they don't bunch up.
            start_idx = (i * len(self.waypoints) // n) % len(self.waypoints)
            v = HostVehicle(
                vehicle_id=f"host_{i}",
                waypoints=self.waypoints,
                speed_mps=speed_mps,
            )
            v.x = self.waypoints[start_idx].x
            v.y = self.waypoints[start_idx].y
            v.target_idx = (start_idx + 1) % len(self.waypoints)
            d = Drone(drone_id=f"drone_{i}", x=v.x, y=v.y)
            tg = TriggerGenerator(config.trigger, self.waypoints, self.rng)
            self.units.append(VehicleUnit(
                vehicle=v, drone=d, trigger_gen=tg,
                color=_VEHICLE_COLORS[i % len(_VEHICLE_COLORS)],
            ))

        self.conditions_model = ConditionsModel(
            config.conditions, config.world, config.simulation, self.rng,
        )
        self.mission_ctrl = MissionController(config, self.rng)
        self.pipeline = DataPipeline(
            config.pipeline, config.probabilities, self.rng,
            emit_packages_to=config.simulation.emit_packages_to,
        )
        self.economics = Economics(config.economics, host_vehicle_count=n)
        self.metrics = Metrics()

        self.completed_missions: list[Mission] = []
        self.completed_jobs: list[PipelineJob] = []

    # -- core loop ----------------------------------------------------------

    def step(self, dt: float | None = None) -> SimSnapshot:
        dt = dt or self.cfg.simulation.dt_seconds
        cond = self.conditions_model.current(self.t_s)
        operating = cond.is_daylight

        for unit in self.units:
            self._step_unit(unit, dt, cond, operating)

        for job in self.pipeline.step(self.t_s):
            self._finalize_pipeline_job(job)

        self.economics.tick(dt, operating=operating)
        self.t_s += dt
        return self.snapshot(cond)

    def _step_unit(
        self,
        unit: VehicleUnit,
        dt: float,
        cond: Conditions,
        operating: bool,
    ) -> None:
        if operating:
            reached_wp = unit.vehicle.update(dt)
        else:
            reached_wp = None

        # Waypoint trigger: vehicle just rolled onto an interesting scene point.
        if reached_wp is not None and operating:
            unit.vehicle.stop_for(self.cfg.host_vehicles.stop_at_waypoint_seconds)
            if unit.drone.state == DroneState.DOCKED and unit.active_mission is None:
                trig = unit.trigger_gen.trigger_on_waypoint(
                    self.t_s, unit.vehicle, reached_wp,
                )
                if trig is not None:
                    self._begin_mission(unit, trig)

        # Poisson trigger arrivals.
        if (
            operating
            and unit.active_mission is None
            and unit.drone.state == DroneState.DOCKED
        ):
            trig = unit.trigger_gen.poll(dt, self.t_s, unit.vehicle)
            if trig is not None:
                self._begin_mission(unit, trig)
        elif operating and unit.trigger_gen.poll(dt, self.t_s, unit.vehicle):
            self.metrics.triggers_skipped_drone_busy += 1

        # Advance the active mission, which also drives the drone's position.
        if unit.active_mission is not None:
            self.mission_ctrl.step(
                unit.active_mission, unit.drone, unit.vehicle, cond, dt, self.t_s,
            )
            if not unit.active_mission.is_active:
                self._finalize_mission(unit.active_mission)
                unit.active_mission = None
        else:
            unit.drone.x, unit.drone.y = unit.vehicle.x, unit.vehicle.y
            unit.drone.altitude_m = 0.0

        unit.drone.charge_or_drain(dt)

    def run_headless(self) -> None:
        while self.t_s < self.duration_s:
            self.step()

    def snapshot(self, cond: Conditions | None = None) -> SimSnapshot:
        cond = cond or self.conditions_model.current(self.t_s)
        return SimSnapshot(
            t_s=self.t_s,
            conditions=cond,
            units=self.units,
            waypoints=self.waypoints,
            metrics=self.metrics,
            economics=self.economics,
            pipeline=self.pipeline,
        )

    # -- internals ----------------------------------------------------------

    def _begin_mission(self, unit: VehicleUnit, trigger: Trigger) -> None:
        # Spec 1.4: launch only if vehicle is stationary or <5 mph.
        if unit.vehicle.speed_mph > 5.0 and not unit.vehicle.stopped:
            self.metrics.triggers_skipped_outside_envelope += 1
            return
        unit.active_mission = self.mission_ctrl.start(
            trigger, unit.vehicle, unit.drone, self.t_s,
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
