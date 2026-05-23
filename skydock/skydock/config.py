"""Config loader: YAML file + CLI dotted-key overrides into typed dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SimulationConfig:
    duration_hours: float = 8.0
    dt_seconds: float = 1.0
    seed: int = 42
    start_hour: float = 7.0    # wall-clock hour the sim begins at (t=0)
    emit_packages_to: str | None = None   # output dir for per-scenario deliverables; None disables


@dataclass
class WorldConfig:
    width_m: float = 5000.0
    height_m: float = 5000.0
    daylight_start_hour: float = 7.0
    daylight_end_hour: float = 18.5


@dataclass
class HostVehicleConfig:
    count: int = 1
    speed_mph_cruise: float = 25.0
    stop_at_waypoint_seconds: float = 90.0
    # Per-vehicle corridor types. If shorter than `count`, the list cycles.
    # Valid types: "urban_dense", "suburban", "highway_mix" (see world.py).
    corridor_types: list[str] = field(default_factory=lambda: ["urban_dense"])


@dataclass
class TriggerConfig:
    poisson_rate_per_hour: float = 3.5
    manual_share: float = 0.55
    waypoint_share: float = 0.30
    hard_brake_share: float = 0.15


@dataclass
class MissionConfig:
    decision_seconds: float = 2.0
    launch_seconds: float = 4.0
    climb_seconds: float = 25.0
    capture_seconds_min: float = 30.0
    capture_seconds_max: float = 120.0
    return_seconds: float = 25.0
    land_seconds: float = 8.0
    target_altitude_m: float = 80.0


@dataclass
class ProbabilityConfig:
    pre_flight_pass: float = 0.88
    launch_success: float = 0.97
    recovery_success: float = 0.98
    upload_success: float = 0.99


@dataclass
class ConditionsConfig:
    wind_mph_base: float = 6.0
    wind_mph_amplitude: float = 8.0
    wind_abort_threshold_mph: float = 20.0
    weather_clear_prob: float = 0.85


@dataclass
class PipelineConfig:
    process_minutes_min: float = 20.0
    process_minutes_max: float = 90.0
    quality_mean: float = 82.0
    quality_std: float = 10.0
    quality_threshold: float = 70.0


@dataclass
class EconomicsConfig:
    price_per_scenario_usd: float = 150.0
    operator_cost_per_hour_usd: float = 30.0
    vehicle_cost_per_hour_usd: float = 5.0
    cloud_cost_per_scenario_usd: float = 0.80
    drone_wear_per_scenario_usd: float = 1.00
    fixed_daily_overhead_usd: float = 220.0


@dataclass
class FailureCascadeConfig:
    """Rare but consequential failures from spec §7.1.

    Each event takes a unit offline for a recovery period — the dominant
    operational risk these model is *fleet downtime*, not per-mission
    failures (which are covered by ProbabilityConfig).
    """
    enabled: bool = True
    drone_flyaway_prob_per_mission: float = 0.002    # spec §7.1: rare flyaway
    drone_replacement_hours: float = 12.0
    dock_damage_prob_per_landing: float = 0.015      # ~1.5% per landing
    dock_repair_hours: float = 6.0
    battery_degradation_per_flight_pct: float = 0.04


@dataclass
class AnimationConfig:
    fps: int = 15
    speed_multiplier: float = 90.0
    trail_length_s: float = 60.0


@dataclass
class Config:
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    world: WorldConfig = field(default_factory=WorldConfig)
    host_vehicles: HostVehicleConfig = field(default_factory=HostVehicleConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    mission: MissionConfig = field(default_factory=MissionConfig)
    probabilities: ProbabilityConfig = field(default_factory=ProbabilityConfig)
    conditions: ConditionsConfig = field(default_factory=ConditionsConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    economics: EconomicsConfig = field(default_factory=EconomicsConfig)
    failure_cascades: FailureCascadeConfig = field(default_factory=FailureCascadeConfig)
    animation: AnimationConfig = field(default_factory=AnimationConfig)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Config":
        cfg = cls()
        if path is None:
            return cfg
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for section, vals in data.items():
            if not hasattr(cfg, section):
                continue
            sub = getattr(cfg, section)
            for key, val in (vals or {}).items():
                if hasattr(sub, key):
                    setattr(sub, key, val)
        return cfg

    def apply_overrides(self, overrides: dict[str, Any]) -> None:
        for dotted, val in overrides.items():
            if "." not in dotted:
                continue
            section, attr = dotted.split(".", 1)
            if not hasattr(self, section):
                continue
            sub = getattr(self, section)
            if not hasattr(sub, attr):
                continue
            existing = getattr(sub, attr)
            if isinstance(existing, list) and isinstance(val, str):
                # Accept "[a,b,c]" or "a,b,c" from the CLI.
                stripped = val.strip().strip("[]")
                val = [s.strip() for s in stripped.split(",") if s.strip()]
            elif existing is None or isinstance(val, type(existing)):
                pass
            else:
                try:
                    val = type(existing)(val)
                except (TypeError, ValueError):
                    pass
            setattr(sub, attr, val)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
