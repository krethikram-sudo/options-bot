#!/usr/bin/env python3
"""Parameter sweep — run N seeds × M parameter combinations headless,
aggregate KPIs, and write a CSV + a summary plot.

The sweep grid is defined in SWEEPS below; edit it or override on the
CLI with --sweep key=val1,val2,val3 (repeatable).

Examples:
    python sweep.py                                              # default grid, 5 seeds
    python sweep.py --seeds 10
    python sweep.py --sweep host_vehicles.count=1,2,3,5 \\
                    --sweep trigger.poisson_rate_per_hour=2.5,5,8
    python sweep.py --workers 4                                  # parallel runs
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import multiprocessing as mp
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from skydock.config import Config
from skydock.simulation import Simulation


# Default sweep grid — meant to surface the parameters that matter most for the MVP.
SWEEPS: dict[str, list[Any]] = {
    "host_vehicles.count": [1, 2, 3, 5],
    "trigger.poisson_rate_per_hour": [2.0, 3.5, 5.0, 7.0],
    "probabilities.pre_flight_pass": [0.80, 0.88, 0.95],
}
DEFAULT_SEEDS = 5
DEFAULT_CONFIG = Path(__file__).parent / "default_config.yaml"


def _coerce(value: str) -> Any:
    v = value.strip()
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _parse_sweep_args(items: list[str]) -> dict[str, list[Any]]:
    grid: dict[str, list[Any]] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--sweep expects key=v1,v2,v3 (got {item!r})")
        key, vals = item.split("=", 1)
        grid[key.strip()] = [_coerce(v) for v in vals.split(",")]
    return grid


def _apply(cfg: Config, overrides: dict[str, Any]) -> None:
    for dotted, val in overrides.items():
        section, attr = dotted.split(".", 1)
        sub = getattr(cfg, section)
        # Preserve target type where the existing value isn't None.
        existing = getattr(sub, attr)
        if existing is not None:
            try:
                val = type(existing)(val)
            except (TypeError, ValueError):
                pass
        setattr(sub, attr, val)


def _run_one(args: tuple[Path, dict[str, Any], int]) -> dict[str, Any]:
    config_path, overrides, seed = args
    cfg = Config.load(config_path) if config_path.exists() else Config()
    _apply(cfg, overrides)
    cfg.simulation.seed = seed
    # Disable per-scenario package emission during sweeps — too much disk noise.
    cfg.simulation.emit_packages_to = None
    sim = Simulation(cfg)
    sim.run_headless()
    m = sim.metrics
    e = sim.economics.ledger
    delivered = sum(1 for j in sim.completed_jobs if j.delivered)
    row = dict(overrides)
    row.update({
        "seed": seed,
        "duration_hours": cfg.simulation.duration_hours,
        "missions_started": m.missions_started,
        "missions_succeeded": m.missions_succeeded,
        "missions_aborted": m.missions_aborted,
        "success_rate": m.success_rate(),
        "delivered": delivered,
        "rejected": sim.pipeline.rejected_count,
        "avg_quality": m.avg_delivered_quality(),
        "revenue_usd": e.revenue_usd,
        "gross_profit_usd": e.gross_profit,
        "gross_margin": e.gross_margin,
    })
    return row


def run_sweep(
    config_path: Path,
    grid: dict[str, list[Any]],
    n_seeds: int,
    workers: int,
    out_dir: Path,
) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = list(grid.keys())
    combos = list(itertools.product(*grid.values()))

    jobs: list[tuple[Path, dict[str, Any], int]] = []
    for combo in combos:
        overrides = dict(zip(keys, combo))
        for seed in range(n_seeds):
            jobs.append((config_path, overrides, seed))

    print(f"sweep: {len(combos)} combos × {n_seeds} seeds = {len(jobs)} runs, "
          f"workers={workers}")

    t0 = time.time()
    if workers <= 1:
        rows = [_run_one(j) for j in jobs]
    else:
        with mp.Pool(workers) as pool:
            rows = pool.map(_run_one, jobs)
    elapsed = time.time() - t0
    print(f"sweep finished in {elapsed:.1f}s")

    csv_path = out_dir / "sweep.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {csv_path}")

    summary_path = out_dir / "sweep_summary.json"
    summary = _summarize(rows, keys)
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"  wrote {summary_path}")

    plot_path = out_dir / "sweep_plot.png"
    _plot_summary(rows, keys, plot_path)
    print(f"  wrote {plot_path}")

    return rows


def _summarize(rows: list[dict[str, Any]], grid_keys: list[str]) -> list[dict[str, Any]]:
    """Group runs by config (everything except seed) and report mean/p10/p90."""
    import statistics

    groups: dict[tuple, list[dict[str, Any]]] = {}
    for r in rows:
        key = tuple(r[k] for k in grid_keys)
        groups.setdefault(key, []).append(r)

    out = []
    metrics = ["missions_started", "missions_succeeded", "delivered",
               "revenue_usd", "gross_profit_usd", "gross_margin", "avg_quality"]
    for key, group in groups.items():
        entry = {k: v for k, v in zip(grid_keys, key)}
        entry["n_seeds"] = len(group)
        for m in metrics:
            vals = [r[m] for r in group]
            entry[f"{m}_mean"] = statistics.fmean(vals)
            if len(vals) >= 2:
                entry[f"{m}_p10"] = _quantile(vals, 0.10)
                entry[f"{m}_p90"] = _quantile(vals, 0.90)
        out.append(entry)
    return out


def _quantile(vals: list[float], q: float) -> float:
    vs = sorted(vals)
    pos = (len(vs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vs) - 1)
    frac = pos - lo
    return vs[lo] * (1 - frac) + vs[hi] * frac


def _plot_summary(rows: list[dict[str, Any]], grid_keys: list[str], path: Path) -> None:
    """Marginal-effect plot: one column per varying parameter, two rows
    (delivered scenarios, revenue). Aggregates over the other params at each
    point so the trend along each axis is visible without 48-bar fan-outs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    varying_keys = [k for k in grid_keys
                    if len({r[k] for r in rows}) > 1]
    if not varying_keys:
        return

    metrics = [("delivered", "Delivered scenarios"),
               ("revenue_usd", "Revenue (USD)")]
    n_cols = len(varying_keys)
    fig, axes = plt.subplots(
        len(metrics), n_cols,
        figsize=(max(9, 3.6 * n_cols), 6.5),
        facecolor="#0e0f12",
        squeeze=False,
    )

    def short(name: str) -> str:
        return name.split(".")[-1].replace("_per_hour", "/h")

    for col, key in enumerate(varying_keys):
        values = sorted({r[key] for r in rows})
        for row_idx, (metric, title) in enumerate(metrics):
            ax = axes[row_idx][col]
            ax.set_facecolor("#16181d")
            for spine in ax.spines.values():
                spine.set_color("#3a3f47")
            ax.tick_params(colors="#9ca3af", labelsize=8)
            ax.grid(axis="y", color="#2a2f37", linewidth=0.5)
            ax.set_axisbelow(True)

            data = [[r[metric] for r in rows if r[key] == v] for v in values]
            bp = ax.boxplot(data, patch_artist=True, showfliers=True, widths=0.55)
            for patch in bp["boxes"]:
                patch.set_facecolor("#3a4252")
                patch.set_edgecolor("#9ca3af")
            for median in bp["medians"]:
                median.set_color("#f5a524")
            for whisker in bp["whiskers"] + bp["caps"]:
                whisker.set_color("#9ca3af")
            ax.set_xticks(range(1, len(values) + 1))
            ax.set_xticklabels([str(v) for v in values], fontsize=9,
                               color="#9ca3af")
            if row_idx == 0:
                ax.set_title(short(key), color="#e5e7eb", fontsize=11, pad=6)
            if col == 0:
                ax.set_ylabel(title, color="#e5e7eb", fontsize=10)

    fig.suptitle("Skydock parameter sweep — marginal effects",
                 color="#e5e7eb", fontsize=13, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=110, facecolor="#0e0f12")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skydock parameter sweep")
    parser.add_argument("--config", "-c", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--sweep", dest="sweeps", action="append", default=[],
                        metavar="key=v1,v2,...",
                        help="Override a sweep axis (repeatable)")
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel sim workers (default: 1)")
    parser.add_argument("--out", type=Path, default=Path("out/sweep"),
                        help="Output directory for csv/json/png")
    args = parser.parse_args(argv)

    grid = dict(SWEEPS)
    grid.update(_parse_sweep_args(args.sweeps))
    if not grid:
        raise SystemExit("sweep grid is empty")

    run_sweep(
        config_path=args.config,
        grid=grid,
        n_seeds=args.seeds,
        workers=args.workers,
        out_dir=args.out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
