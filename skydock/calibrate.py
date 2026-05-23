#!/usr/bin/env python3
"""Calibrate the sim against spec §6.1 / §1.5 targets.

Runs N seeds at the current config and reports the distribution of
each KPI vs its spec target. Use this to decide whether the priors
in default_config.yaml are realistic and to find which knobs to tune.

Example:
    python calibrate.py --seeds 12             # default day, 1 vehicle
    python calibrate.py --seeds 12 --vehicles 3
    python calibrate.py --month-six             # apply month-6 priors and re-run
"""
from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from skydock.config import Config
from skydock.simulation import Simulation


DEFAULT_CONFIG = Path(__file__).parent / "default_config.yaml"


@dataclass
class Target:
    """A spec target — extractor returns the run's value, threshold compares it."""
    name: str
    spec_ref: str
    extractor: Callable[[Simulation], float]
    threshold: Callable[[float], bool]
    target_str: str
    unit: str = ""


def _delivered(sim: Simulation) -> int:
    return sum(1 for j in sim.completed_jobs if j.delivered)


def _avg_mission_seconds(sim: Simulation) -> float:
    successful = [m for m in sim.completed_missions if m.stage == "DONE"]
    if not successful:
        return 0.0
    return statistics.fmean(
        m.completed_at_s - m.started_at_s for m in successful if m.completed_at_s
    )


def _avg_capture_to_delivery_hours(sim: Simulation) -> float:
    delivered = [j for j in sim.completed_jobs if j.delivered]
    if not delivered:
        return 0.0
    return statistics.fmean(
        (j.finish_at_s - j.mission.started_at_s) / 3600.0 for j in delivered
    )


def _recovery_success_rate(sim: Simulation) -> float:
    landings = sum(1 for m in sim.completed_missions
                   if m.stage == "DONE" or m.aborted_reason == "dock_latch_fail")
    if landings == 0:
        return 1.0
    fails = sum(1 for m in sim.completed_missions
                if m.aborted_reason == "dock_latch_fail")
    return 1.0 - fails / landings


def _captures_per_operating_day(sim: Simulation) -> float:
    """Spec §1.5 defines an operating day as ~11h. Normalize to that."""
    operating_day_hours = 11.0
    if sim.cfg.simulation.duration_hours <= 0:
        return 0.0
    succeeded = sum(1 for m in sim.completed_missions if m.stage == "DONE")
    # Per-vehicle captures normalized to one 11h operating day.
    n_vehicles = max(1, len(sim.units))
    return succeeded * (operating_day_hours / sim.cfg.simulation.duration_hours) / n_vehicles


# Spec §6.1 / §1.5 targets.
TARGETS: list[Target] = [
    Target(
        name="captures / vehicle-day",
        spec_ref="§1.5",
        extractor=_captures_per_operating_day,
        threshold=lambda v: 12.0 <= v <= 20.0,
        target_str="12-20",
    ),
    Target(
        name="mission success rate",
        spec_ref="§6.1",
        extractor=lambda s: s.metrics.success_rate(),
        threshold=lambda v: v >= 0.90,
        target_str="≥ 90 %",
        unit="%",
    ),
    Target(
        name="recovery success rate",
        spec_ref="§6.1",
        extractor=_recovery_success_rate,
        threshold=lambda v: v >= 0.99,
        target_str="≥ 99 %",
        unit="%",
    ),
    Target(
        name="avg delivered quality",
        spec_ref="§6.1",
        extractor=lambda s: s.metrics.avg_delivered_quality(),
        threshold=lambda v: v >= 80.0,
        target_str="≥ 80",
    ),
    Target(
        name="capture → delivery time",
        spec_ref="§6.1",
        extractor=_avg_capture_to_delivery_hours,
        threshold=lambda v: v <= 4.0,
        target_str="≤ 4 h",
        unit="h",
    ),
    Target(
        name="mission completion time",
        spec_ref="§6.1",
        extractor=_avg_mission_seconds,
        threshold=lambda v: v <= 120.0,
        target_str="≤ 120 s",
        unit="s",
    ),
    Target(
        name="gross margin",
        spec_ref="§4.3",
        extractor=lambda s: s.economics.ledger.gross_margin,
        threshold=lambda v: v >= 0.78,
        target_str="≥ 78 %",
        unit="%",
    ),
]


# Tuned priors representing "month-6 operational maturity" from spec §6.1.
# Each override has a plausible operational interpretation:
#   - tighter pre-flight checklist
#   - weather-day rescheduling (don't fly bad-weather days, so weather_clear conditional on flying day)
#   - refined flight profiles (faster climb / return)
#   - more capable processing pipeline (parallelized → lower max latency)
MONTH_SIX_OVERRIDES: dict[str, float] = {
    "trigger.poisson_rate_per_hour": 2.0,
    "probabilities.pre_flight_pass": 0.96,
    "probabilities.launch_success": 0.99,
    "probabilities.recovery_success": 0.995,
    "probabilities.upload_success": 0.995,
    "conditions.weather_clear_prob": 0.95,
    "mission.climb_seconds": 18.0,
    "mission.return_seconds": 18.0,
    "mission.capture_seconds_max": 75.0,
    "pipeline.process_minutes_max": 60.0,
    "pipeline.quality_mean": 86.0,
    "pipeline.quality_std": 7.0,
}


def _apply_overrides(cfg: Config, overrides: dict[str, float]) -> None:
    for dotted, val in overrides.items():
        section, attr = dotted.split(".", 1)
        sub = getattr(cfg, section)
        setattr(sub, attr, type(getattr(sub, attr))(val))


def _quantile(vals: list[float], q: float) -> float:
    vs = sorted(vals)
    pos = (len(vs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vs) - 1)
    frac = pos - lo
    return vs[lo] * (1 - frac) + vs[hi] * frac


def _fmt(v: float, unit: str) -> str:
    if unit == "%":
        return f"{v * 100:5.1f} %"
    if unit == "h":
        return f"{v:5.2f} h"
    if unit == "s":
        return f"{v:5.0f} s"
    return f"{v:5.1f}"


def run_calibration(
    config_path: Path,
    n_seeds: int,
    overrides: dict[str, float],
    label: str,
) -> tuple[list[dict[str, float]], dict[str, dict[str, float]]]:
    print()
    print("=" * 72)
    print(f"Calibration: {label}  ({n_seeds} seeds)")
    print("=" * 72)

    runs: list[dict[str, float]] = []
    for seed in range(n_seeds):
        cfg = Config.load(config_path) if config_path.exists() else Config()
        _apply_overrides(cfg, overrides)
        cfg.simulation.seed = seed
        cfg.simulation.emit_packages_to = None  # don't litter disk during calibration
        sim = Simulation(cfg)
        sim.run_headless()
        runs.append({t.name: t.extractor(sim) for t in TARGETS})

    summary: dict[str, dict[str, float]] = {}
    for t in TARGETS:
        vals = [r[t.name] for r in runs]
        summary[t.name] = {
            "mean": statistics.fmean(vals),
            "p10": _quantile(vals, 0.10),
            "p90": _quantile(vals, 0.90),
            "pass_rate": sum(1 for v in vals if t.threshold(v)) / len(vals),
        }

    print(f"\n  {'metric':<26} {'target':<14} {'mean':>10} "
          f"{'p10':>10} {'p90':>10}   pass rate")
    print(f"  {'-' * 26} {'-' * 14} {'-' * 10} {'-' * 10} {'-' * 10}   {'-' * 9}")
    for t in TARGETS:
        s = summary[t.name]
        mean_str = _fmt(s["mean"], t.unit)
        p10_str = _fmt(s["p10"], t.unit)
        p90_str = _fmt(s["p90"], t.unit)
        passed = "✓" if t.threshold(s["mean"]) else "✗"
        print(
            f"  {t.name:<26} {t.target_str:<14} {mean_str:>10} "
            f"{p10_str:>10} {p90_str:>10}   {passed} {s['pass_rate']*100:4.0f}%"
            f"   ({t.spec_ref})"
        )

    return runs, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skydock spec-target calibration")
    parser.add_argument("--config", "-c", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--vehicles", type=int, default=1)
    parser.add_argument("--month-six", action="store_true",
                        help="Apply month-6 maturity overrides before running.")
    parser.add_argument("--both", action="store_true",
                        help="Run defaults AND month-six in one go for comparison.")
    args = parser.parse_args(argv)

    base_overrides: dict[str, float] = {"host_vehicles.count": args.vehicles}

    if args.both:
        run_calibration(args.config, args.seeds, base_overrides, "v0 defaults")
        run_calibration(args.config, args.seeds,
                        {**base_overrides, **MONTH_SIX_OVERRIDES},
                        "month-6 priors")
    elif args.month_six:
        run_calibration(args.config, args.seeds,
                        {**base_overrides, **MONTH_SIX_OVERRIDES},
                        "month-6 priors")
    else:
        run_calibration(args.config, args.seeds, base_overrides, "current defaults")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
