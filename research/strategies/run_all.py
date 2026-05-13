"""Run every strategy + benchmark + dump comparative table.

Usage:
    cd ~/options-bot
    ./venv/bin/python -m research.strategies.run_all

Writes:
    research/strategies/results.csv     # metrics for every strategy
    research/strategies/equity_curves.parquet  # daily portfolio value per strategy
"""
from __future__ import annotations

from pathlib import Path
import time

import pandas as pd
from tabulate import tabulate

from research.data_lib import category
from research.strategies.framework import BacktestResult
from research.strategies.strategies import (
    benchmark_60_40,
    benchmark_buy_hold,
    benchmark_equal_weight,
    pairs_trade_basket,
    quality_trend_composite,
    regime_gated_universe,
    risk_parity_overlay,
    thematic_basket,
    vol_targeted_trend,
    xs_momentum_ai9,
    xs_momentum_universe,
)

OUT_DIR = Path(__file__).resolve().parent
RESULTS_CSV = OUT_DIR / "results.csv"
EQUITY_PARQUET = OUT_DIR / "equity_curves.parquet"


def run_all() -> list[BacktestResult]:
    runs: list[BacktestResult] = []

    # ---- benchmarks ----
    print("\n[benchmarks]")
    for r in [
        benchmark_buy_hold("SPY", "bench_spy"),
        benchmark_buy_hold("QQQ", "bench_qqq"),
        benchmark_buy_hold("NVDA", "bench_nvda"),
        benchmark_equal_weight(category("core_ai_infra"), "bench_ew_ai9"),
        benchmark_60_40(),
    ]:
        runs.append(r)
        print(f"  ✓ {r.name}: CAGR={r.metrics.get('cagr', 0)*100:.1f}%")

    # ---- candidate strategies ----
    print("\n[candidate strategies]")
    candidates = [
        ("xs_momentum_ai9", lambda: xs_momentum_ai9(top_n=3, rebalance="monthly")),
        ("xs_momentum_universe", lambda: xs_momentum_universe(top_n=5, rebalance="monthly")),
        ("quality_trend_composite", lambda: quality_trend_composite(top_n=4)),
        ("pairs_trade_basket", lambda: pairs_trade_basket()),
        ("vol_targeted_trend", lambda: vol_targeted_trend()),
        ("power_infra_basket", lambda: thematic_basket(
            "power_infra_basket", ["VRT", "GEV", "CEG", "ETN", "HUBB"])),
        ("networking_basket", lambda: thematic_basket(
            "networking_basket", ["ANET", "LITE", "CRDO", "COHR", "CIEN"])),
        ("wfe_basket", lambda: thematic_basket(
            "wfe_basket", ["ASML", "AMAT", "KLAC", "LRCX", "TER"])),
        ("regime_gated_universe", lambda: regime_gated_universe()),
        ("risk_parity_overlay", lambda: risk_parity_overlay()),
    ]
    for label, fn in candidates:
        t0 = time.time()
        try:
            r = fn()
            runs.append(r)
            print(f"  ✓ {r.name}: CAGR={r.metrics.get('cagr', 0)*100:.1f}%  "
                  f"Sharpe={r.metrics.get('sharpe', 0):.2f}  "
                  f"DD={r.metrics.get('max_dd', 0)*100:.1f}%  "
                  f"({time.time()-t0:.1f}s)")
        except Exception as e:
            print(f"  ✗ {label}: ERROR {e}")
    return runs


def write_results(runs: list[BacktestResult]) -> None:
    rows = []
    eq_cols = {}
    for r in runs:
        m = r.metrics or {}
        rows.append({
            "strategy": r.name,
            "cagr_pct": round(m.get("cagr", 0) * 100, 2),
            "total_return_pct": round(m.get("total_return", 0) * 100, 2),
            "vol_pct": round(m.get("vol", 0) * 100, 2),
            "sharpe": round(m.get("sharpe", 0), 2),
            "sortino": round(m.get("sortino", 0), 2),
            "calmar": round(m.get("calmar", 0), 2),
            "max_dd_pct": round(m.get("max_dd", 0) * 100, 2),
            "hit_rate_daily": round(m.get("hit_rate_daily", 0), 3),
            "n_days": m.get("n_days", 0),
            "years": round(m.get("years", 0), 2),
            "n_trades": len(r.trades),
        })
        if not r.equity.empty:
            eq_cols[r.name] = r.equity

    df = pd.DataFrame(rows).sort_values("sharpe", ascending=False)
    df.to_csv(RESULTS_CSV, index=False)
    print(f"\nResults → {RESULTS_CSV}")
    print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))

    if eq_cols:
        eq_df = pd.DataFrame(eq_cols)
        eq_df.to_parquet(EQUITY_PARQUET)
        print(f"Equity curves → {EQUITY_PARQUET}")


if __name__ == "__main__":
    runs = run_all()
    write_results(runs)
