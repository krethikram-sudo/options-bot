#!/usr/bin/env python3
"""Skydock simulation CLI.

Examples:
    python run.py                          # headless, default config, prints report
    python run.py --animate                # live matplotlib animation
    python run.py --save out.mp4           # save animation to file
    python run.py --config my.yaml         # use custom config file
    python run.py --set simulation.duration_hours=4 --set trigger.poisson_rate_per_hour=5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skydock.animation import run_animation
from skydock.config import Config
from skydock.report import print_report
from skydock.simulation import Simulation


def _parse_overrides(items: list[str]) -> dict:
    out = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got: {item}")
        k, v = item.split("=", 1)
        # Best-effort type coercion: int, float, bool, else str.
        v_strip = v.strip()
        if v_strip.lower() in ("true", "false"):
            out[k.strip()] = v_strip.lower() == "true"
            continue
        try:
            out[k.strip()] = int(v_strip)
            continue
        except ValueError:
            pass
        try:
            out[k.strip()] = float(v_strip)
            continue
        except ValueError:
            pass
        out[k.strip()] = v_strip
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skydock drone simulation")
    parser.add_argument(
        "--config", "-c", type=Path, default=Path(__file__).parent / "default_config.yaml",
        help="Path to YAML config (default: default_config.yaml)",
    )
    parser.add_argument(
        "--set", dest="overrides", action="append", default=[],
        metavar="key.path=value",
        help="Dotted-key override (repeatable). e.g. --set trigger.poisson_rate_per_hour=5",
    )
    parser.add_argument(
        "--animate", "-a", action="store_true",
        help="Launch interactive matplotlib animation instead of headless run.",
    )
    parser.add_argument(
        "--save", type=Path, default=None,
        help="Save animation to file (mp4 or gif). Implies --animate.",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Override the random seed.",
    )
    parser.add_argument(
        "--emit-packages", type=Path, default=None,
        help="Write a metadata.json + agent_tracks.json + scenario.xosc package "
             "for every delivered scenario into this directory.",
    )
    parser.add_argument(
        "--vehicles", type=int, default=None,
        help="Shortcut for --set host_vehicles.count=N",
    )
    args = parser.parse_args(argv)

    cfg = Config.load(args.config) if args.config and args.config.exists() else Config()
    if args.seed is not None:
        cfg.simulation.seed = args.seed
    if args.emit_packages is not None:
        cfg.simulation.emit_packages_to = str(args.emit_packages)
    if args.vehicles is not None:
        cfg.host_vehicles.count = args.vehicles
    cfg.apply_overrides(_parse_overrides(args.overrides))

    sim = Simulation(cfg)

    animate = args.animate or args.save is not None
    if animate:
        run_animation(sim, save_path=str(args.save) if args.save else None)
        # Still print a report after the animation ends.
        print_report(sim)
    else:
        sim.run_headless()
        print_report(sim)
    return 0


if __name__ == "__main__":
    sys.exit(main())
