"""Walk-forward validation of the top strategies.

Re-runs each top strategy and slices its equity curve into 4 sub-windows:
  W1: 2024-03 → 2024-09 (pre-DeepSeek)
  W2: 2024-10 → 2025-03 (DeepSeek shock + recovery)
  W3: 2025-04 → 2025-12 (rotation)
  W4: 2026-01 → 2026-05 (current)

For each window: CAGR (annualized), vol, Sharpe, MaxDD. A strategy is "robust"
if Sharpe stays positive (>0.5) across all 4 windows. Strategies that win on
total period but fail one window are likely overfit to that period's regime.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from tabulate import tabulate

from research.strategies.engine import Strategy, run_strategy
from research.strategies.framework import metrics

WINDOWS = [
    ("W1_2024H1", "2024-03-04", "2024-09-30"),
    ("W2_DeepSeek", "2024-10-01", "2025-03-31"),
    ("W3_2025_rotation", "2025-04-01", "2025-12-31"),
    ("W4_2026YTD", "2026-01-01", "2026-05-01"),
]

TOP_STRATEGIES = [
    Strategy(1, "memory_pair", "concentrated_basket",
             "MU+SNDK champion (regime-specific)",
             {"signal": "equal_weight", "universe": ["MU", "SNDK"], "rebalance": "monthly"}),
    Strategy(2, "ai_silicon_only", "equal_weight",
             "EW silicon-only universe (top of full search)",
             {"signal": "equal_weight", "universe": "ai_silicon_only", "rebalance": "monthly"}),
    Strategy(3, "ai_full_chain", "equal_weight",
             "EW full AI value chain",
             {"signal": "equal_weight", "universe": "ai_full_chain", "rebalance": "monthly"}),
    Strategy(4, "qt_full_chain", "xs_quality_trend",
             "Quality+trend on full chain",
             {"signal": "xs_quality_trend", "universe": "ai_full_chain",
              "sharpe_window": 60, "trend_window": 126, "top_n": 5, "rebalance": "monthly"}),
    Strategy(5, "xsmom_top3", "xs_momentum",
             "xs-momentum top-3 monthly on AI-9 (best active)",
             {"signal": "xs_momentum", "universe": "ai9", "lookback": 252,
              "skip": 21, "top_n": 3, "rebalance": "monthly"}),
    Strategy(6, "xsmom_universe_top5", "xs_momentum",
             "xs-momentum top-5 monthly on full chain",
             {"signal": "xs_momentum", "universe": "ai_full_chain", "lookback": 252,
              "skip": 21, "top_n": 5, "rebalance": "monthly"}),
    Strategy(7, "ai_optics", "concentrated_basket",
             "AI optics basket LITE+COHR+CIEN",
             {"signal": "equal_weight", "universe": ["LITE", "COHR", "CIEN"],
              "rebalance": "monthly"}),
    Strategy(8, "ai_networking", "equal_weight",
             "EW networking basket ANET+LITE+CRDO+COHR+CIEN",
             {"signal": "equal_weight",
              "universe": ["ANET", "LITE", "CRDO", "COHR", "CIEN"],
              "rebalance": "monthly"}),
]


def slice_metrics(equity: pd.Series, start: str, end: str) -> dict:
    """Compute window-specific metrics by slicing the equity curve."""
    s = pd.to_datetime(start)
    e = pd.to_datetime(end)
    sub = equity.loc[(equity.index >= s) & (equity.index <= e)]
    if len(sub) < 10:
        return {}
    # rebase to 100 for clarity
    sub = sub / sub.iloc[0] * 100
    return metrics(sub)


def run_walkforward() -> pd.DataFrame:
    rows = []
    for strat in TOP_STRATEGIES:
        print(f"Running {strat.name}...")
        try:
            r = run_strategy(strat)
        except Exception as ex:
            print(f"  ERROR: {ex}")
            continue
        if r.equity.empty:
            print(f"  no equity curve")
            continue
        full = r.metrics
        row = {
            "strategy": strat.name,
            "full_cagr": round(full.get("cagr", 0) * 100, 1),
            "full_sharpe": round(full.get("sharpe", 0), 2),
            "full_dd": round(full.get("max_dd", 0) * 100, 1),
        }
        for label, start, end in WINDOWS:
            m = slice_metrics(r.equity, start, end)
            if not m:
                row[f"{label}_sharpe"] = None
                row[f"{label}_ret"] = None
                row[f"{label}_dd"] = None
            else:
                # for short windows, "total return" is more meaningful than CAGR
                total_ret = m.get("total_return", 0)
                row[f"{label}_ret"] = round(total_ret * 100, 1)
                row[f"{label}_sharpe"] = round(m.get("sharpe", 0), 2)
                row[f"{label}_dd"] = round(m.get("max_dd", 0) * 100, 1)
        # Robustness: count windows with positive return AND sharpe > 0.5
        win_count = sum(
            1 for label, *_ in WINDOWS
            if row.get(f"{label}_ret") is not None
            and row[f"{label}_ret"] > 0
            and row[f"{label}_sharpe"] is not None
            and row[f"{label}_sharpe"] > 0.5
        )
        row["robust_windows"] = win_count
        rows.append(row)
    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    df = run_walkforward()
    print()
    print("=== WALK-FORWARD VALIDATION ===")
    cols = ["strategy", "full_cagr", "full_sharpe", "full_dd"]
    for label, *_ in WINDOWS:
        cols.extend([f"{label}_ret", f"{label}_sharpe", f"{label}_dd"])
    cols.append("robust_windows")
    print(tabulate(df[cols], headers="keys", tablefmt="simple", showindex=False))

    # Save
    from pathlib import Path
    out = Path(__file__).resolve().parent / "walkforward_results.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")

    print()
    print("=== ROBUSTNESS RANKING (positive AND Sharpe>0.5 in N windows) ===")
    df_sorted = df.sort_values(["robust_windows", "full_sharpe"], ascending=[False, False])
    print(tabulate(df_sorted[["strategy", "robust_windows", "full_sharpe", "full_cagr", "full_dd"]],
                   headers="keys", tablefmt="simple", showindex=False))
