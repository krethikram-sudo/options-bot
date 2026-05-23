"""Config loader: YAML file + CLI dotted-key overrides into typed dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from .dock import DockConfig


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
    # Spec §1.3 sources:
    #   - Poisson source covers `manual` + `hard_brake` (continuous, operator-driven)
    #   - Waypoint source fires when the vehicle reaches a pre-planned scene waypoint
    # The two are independent (no double-counting). Base rate is per host vehicle
    # per operating hour, then multiplied by the corridor's rate_multiplier.
    poisson_rate_per_hour: float = 1.2
    manual_share: float = 0.78       # of Poisson, share that maps to "manual"
    hard_brake_share: float = 0.22   # the rest of Poisson is "hard_brake"
    waypoint_trigger_prob: float = 0.10  # per-waypoint visit, prob of "interesting"


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
    # Battery-aware RTL: spec §1.4 has a 40% pre-flight gate but doesn't cover
    # in-flight low-battery. Realistic drones trigger return-to-launch at ~25%
    # and crash near 5%.
    rtl_battery_threshold_pct: float = 25.0
    crash_battery_threshold_pct: float = 5.0


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
    # Wind gusts: occasional transient impulses on top of the steady-state wind.
    # Real-world drones see these regularly even on otherwise calm days.
    gust_prob_per_second: float = 0.006
    gust_magnitude_mph_min: float = 8.0
    gust_magnitude_mph_max: float = 14.0
    gust_decay_per_second: float = 0.55


@dataclass
class GPSConfig:
    """GPS uncertainty on the host vehicle's reported position.

    The drone reads host position via comms link; below ~10m AGL the
    onboard precision-landing system (vision + BLE beacons) takes over
    and sees the actual dock (bypassing GPS noise).
    """
    host_position_sigma_m: float = 1.25     # ~2.5m 2σ — consumer GPS
    resample_interval_s: float = 2.5        # spatial correlation timescale


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
class CustomerFunnelConfig:
    """Spec §4.1-4.3 — prospect → pilot → paid scenarios pipeline.

    When `enabled=True`, scenario revenue comes from allocating deliveries
    against active pilot commitments at each pilot's negotiated price.
    When disabled (default), revenue is flat per spec §4.2 base tier.
    """
    enabled: bool = False
    prospect_arrival_per_month: float = 2.0       # leads / month from outreach
    prospect_lifetime_days: float = 60.0          # how long a lead stays warm
    prospect_quality_min: float = 78.0            # picky vs not-picky prospects
    prospect_quality_max: float = 88.0
    daily_conversion_prob: float = 0.05           # ~75% over 30 days if quality OK
    scenarios_per_pilot_min: int = 100            # spec §4.2 volume tiers
    scenarios_per_pilot_max: int = 600
    starting_cash_usd: float = 700_000.0          # spec §5.5 MVP budget upper
    fixed_monthly_burn_usd: float = 40_000.0      # spec §5.4 Phase-3 burn


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
    customer_funnel: CustomerFunnelConfig = field(default_factory=CustomerFunnelConfig)
    dock: DockConfig = field(default_factory=DockConfig)
    gps: GPSConfig = field(default_factory=GPSConfig)
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
