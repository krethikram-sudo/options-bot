"""Top-level simulation orchestrator wiring all subsystems."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .conditions import Conditions, ConditionsModel
from .config import Config
from .customer import CustomerFunnel
from .drone import Drone, DroneState
from .economics import Economics
from .metrics import Metrics
from .mission import Mission, MissionController
from .pipeline import DataPipeline, PipelineJob
from .scene import SceneGenerator, TrafficScene, agents_in_footprint
from .triggers import Trigger, TriggerGenerator
from .vehicle import HostVehicle
from .world import Corridor, Waypoint, generate_corridor, split_world_into_bboxes


@dataclass
class VehicleUnit:
    """One host vehicle + its drone + the trigger generator that schedules its missions."""
    vehicle: HostVehicle
    drone: Drone
    trigger_gen: TriggerGenerator
    corridor: Corridor
    active_mission: Optional[Mission] = None
    active_scene: Optional[TrafficScene] = None    # populated during CAPTURING
    capture_frame_idx: int = 0
    color: str = "#9ee37d"
    # Spec §7.1 — when set, unit is offline (no triggers / no missions) until t_s
    # reaches this value. Reason explains the downtime in the dashboard.
    offline_until_s: float = 0.0
    offline_reason: Optional[str] = None

    def is_offline(self, t_s: float) -> bool:
        return t_s < self.offline_until_s


@dataclass
class SimSnapshot:
    """Read-only view of sim state used by the animation."""
    t_s: float
    conditions: Conditions
    units: list[VehicleUnit]
    corridors: list[Corridor]
    metrics: Metrics
    economics: Economics
    pipeline: DataPipeline
    funnel: Optional[CustomerFunnel] = None


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

        n = max(1, int(config.host_vehicles.count))
        types = list(config.host_vehicles.corridor_types) or ["urban_dense"]

        # Build one Corridor per distinct type — vehicles assigned the same
        # type share a corridor (and its waypoints).
        unique_types: list[str] = []
        for t in types:
            if t not in unique_types:
                unique_types.append(t)
        bboxes = split_world_into_bboxes(
            config.world.width_m, config.world.height_m, len(unique_types),
        )
        self.corridors: list[Corridor] = [
            generate_corridor(
                bbox=bbox, corridor_type=t, name=f"{t}_{i}", rng=self.rng,
            )
            for i, (t, bbox) in enumerate(zip(unique_types, bboxes))
        ]
        corridor_by_type = {c.corridor_type: c for c in self.corridors}

        speed_mps = config.host_vehicles.speed_mph_cruise / 2.23694
        self.units: list[VehicleUnit] = []
        for i in range(n):
            assigned_type = types[i % len(types)]
            corridor = corridor_by_type[assigned_type]
            wps = corridor.waypoints
            start_idx = (i * len(wps) // max(n, 1)) % len(wps)
            v = HostVehicle(
                vehicle_id=f"host_{i}",
                waypoints=wps,
                speed_mps=speed_mps,
            )
            v.x = wps[start_idx].x
            v.y = wps[start_idx].y
            v.target_idx = (start_idx + 1) % len(wps)
            d = Drone(drone_id=f"drone_{i}")
            d.physics.snap_to(v.x, v.y, 0.0)
            # Each unit gets its own trigger generator with the corridor's rate multiplier.
            unit_trigger_cfg = type(config.trigger)(
                poisson_rate_per_hour=(
                    config.trigger.poisson_rate_per_hour * corridor.rate_multiplier
                ),
                manual_share=config.trigger.manual_share,
                hard_brake_share=config.trigger.hard_brake_share,
                waypoint_trigger_prob=config.trigger.waypoint_trigger_prob,
            )
            tg = TriggerGenerator(unit_trigger_cfg, wps, self.rng)
            self.units.append(VehicleUnit(
                vehicle=v, drone=d, trigger_gen=tg, corridor=corridor,
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
        self.funnel: Optional[CustomerFunnel] = (
            CustomerFunnel(config.customer_funnel, self.rng)
            if config.customer_funnel.enabled else None
        )
        self.scene_gen = SceneGenerator(self.rng)

        self.completed_missions: list[Mission] = []
        self.completed_jobs: list[PipelineJob] = []
        # Accumulator for daylight operating seconds — used by calibrate.py to
        # normalize "captures per vehicle-day" without assuming the whole sim
        # ran during operating hours.
        self.operating_seconds: float = 0.0

    # -- core loop ----------------------------------------------------------

    def step(self, dt: float | None = None) -> SimSnapshot:
        dt = dt or self.cfg.simulation.dt_seconds
        cond = self.conditions_model.current(self.t_s)
        operating = cond.is_daylight

        for unit in self.units:
            self._step_unit(unit, dt, cond, operating)

        for job in self.pipeline.step(self.t_s):
            self._finalize_pipeline_job(job)

        if self.funnel is not None:
            self.funnel.maybe_tick_day(self.t_s)

        if operating:
            self.operating_seconds += dt
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
        # Spec §7.1 — if the unit is offline (drone lost / dock damaged),
        # the host vehicle returns to a depot and waits. No driving, no triggers.
        if unit.is_offline(self.t_s):
            unit.drone.x, unit.drone.y = unit.vehicle.x, unit.vehicle.y
            unit.drone.altitude_m = 0.0
            return
        if unit.offline_reason is not None and self.t_s >= unit.offline_until_s:
            # Coming back online — if the drone was lost, swap in a replacement.
            if unit.drone.state == DroneState.LOST:
                replacement_id = f"{unit.drone.drone_id}_r{unit.drone.flight_count}"
                unit.drone = Drone(drone_id=replacement_id)
                unit.drone.physics.snap_to(unit.vehicle.x, unit.vehicle.y, 0.0)
            unit.offline_reason = None

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
            trig = unit.trigger_gen.poll(dt, self.t_s, unit.vehicle, rate_multiplier=cond.traffic_factor)
            if trig is not None:
                self._begin_mission(unit, trig)
        elif operating and unit.trigger_gen.poll(dt, self.t_s, unit.vehicle, rate_multiplier=cond.traffic_factor):
            self.metrics.triggers_skipped_drone_busy += 1

        # Advance the active mission, which also drives the drone's position.
        if unit.active_mission is not None:
            prev_stage = unit.active_mission.stage
            self.mission_ctrl.step(
                unit.active_mission, unit.drone, unit.vehicle, cond, dt, self.t_s,
            )
            cur_stage = unit.active_mission.stage

            # Scene lifecycle: spawn at CAPTURING entry, observe each tick,
            # finalize at CAPTURING exit.
            if prev_stage != "CAPTURING" and cur_stage == "CAPTURING":
                self._spawn_scene(unit)
            if cur_stage == "CAPTURING" and unit.active_scene is not None:
                self._observe_scene(unit)
            if prev_stage == "CAPTURING" and cur_stage != "CAPTURING":
                self._finalize_scene(unit)

            if not unit.active_mission.is_active:
                self._finalize_mission(unit.active_mission, unit)
                unit.active_mission = None
        else:
            # Idle — drone sits on the vehicle dock.
            unit.drone.physics.snap_to(unit.vehicle.x, unit.vehicle.y, 0.0)

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
            corridors=self.corridors,
            metrics=self.metrics,
            economics=self.economics,
            pipeline=self.pipeline,
            funnel=self.funnel,
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
        # Spec §1.2 V1 envelope: vehicle must be stationary throughout the
        # mission. Pin it in place until the mission terminates.
        mission_budget_s = (
            self.cfg.mission.decision_seconds
            + self.cfg.mission.launch_seconds * 2
            + self.cfg.mission.climb_seconds * 3
            + self.cfg.mission.capture_seconds_max
            + self.cfg.mission.return_seconds * 3
            + self.cfg.mission.land_seconds * 3
            + 30.0
        )
        unit.vehicle.stop_for(mission_budget_s)

    def _finalize_mission(self, mission: Mission, unit: VehicleUnit) -> None:
        self.completed_missions.append(mission)
        # Vehicle is free to drive again now that the drone is docked / lost.
        unit.vehicle.stopped = False
        unit.vehicle.stop_seconds_remaining = 0.0

        if mission.stage == "DONE":
            self.metrics.on_mission_success(mission.scene_class)
            self.pipeline.enqueue(mission, self.t_s)
            if mission.early_rtl_battery:
                self.metrics.battery_rtl_events += 1
        else:
            reason = mission.aborted_reason or "unknown"
            self.metrics.on_mission_abort(reason)

        # Apply failure-cascade outcomes (spec §7.1) — set unit downtime.
        cascades = self.cfg.failure_cascades
        if mission.drone_lost:
            unit.offline_until_s = self.t_s + cascades.drone_replacement_hours * 3600
            unit.offline_reason = "drone_lost"
            self.metrics.drone_lost_events += 1
        elif mission.dock_damaged:
            unit.offline_until_s = self.t_s + cascades.dock_repair_hours * 3600
            unit.offline_reason = "dock_damaged"
            self.metrics.dock_damage_events += 1

    # -- scene lifecycle ----------------------------------------------------

    def _spawn_scene(self, unit: VehicleUnit) -> None:
        m = unit.active_mission
        if m is None:
            return
        unit.active_scene = self.scene_gen.generate(
            scene_class=m.scene_class,
            center_x=m.capture_x,
            center_y=m.capture_y,
            t_s=self.t_s,
        )
        unit.capture_frame_idx = 0

    def _observe_scene(self, unit: VehicleUnit) -> None:
        scene = unit.active_scene
        if scene is None:
            return
        # 1 sim-tick == 1 "frame" for FOV bookkeeping (lower than 30fps real
        # video but enough for visibility accounting at 1 Hz).
        positions = scene.positions_now(self.t_s)
        visible = agents_in_footprint(
            unit.drone.physics.x, unit.drone.physics.y,
            unit.drone.coverage_radius_m, positions,
        )
        cond = self.conditions_model.current(self.t_s)
        scene.record_observation(
            unit.capture_frame_idx, visible,
            drone_altitude_m=unit.drone.altitude_m,
            wind_mph=cond.wind_mph,
        )
        unit.capture_frame_idx += 1
        # Top up agents that have left the scene so density stays steady
        # through long captures (otherwise FOV slowly drains over time).
        scene.cull_and_respawn(self.t_s, self.scene_gen)

    def _finalize_scene(self, unit: VehicleUnit) -> None:
        scene = unit.active_scene
        if scene is None:
            return
        q = scene.derived_quality_score()
        if unit.active_mission is not None:
            unit.active_mission.quality_score_from_scene = q
        # Hand scene to the mission for the deliverable payload.
        self._attach_scene_to_mission(unit.active_mission, scene)
        unit.active_scene = None

    def _attach_scene_to_mission(self, mission: Optional[Mission], scene: TrafficScene) -> None:
        if mission is None:
            return
        # Stash the scene on the mission object so the pipeline / deliverable
        # emitter can read it. Using setattr to avoid a frozen-field dataclass concern.
        mission.captured_scene = scene  # type: ignore[attr-defined]

    def _finalize_pipeline_job(self, job: PipelineJob) -> None:
        self.completed_jobs.append(job)
        if not job.delivered:
            return
        self.metrics.on_delivery(job.quality_score)
        if self.funnel is None:
            self.economics.record_delivery()
            return
        pilot = self.funnel.allocate_delivery(job.quality_score)
        if pilot is not None:
            self.economics.record_delivery(price=pilot.price_per_scenario)
        else:
            # Generated and processed, but no active pilot to buy it.
            self.economics.record_unsold_delivery()
