"""Grid-search tuner.

Usage from CLI:
    python run.py tune                 # all tickers, default grid
    python run.py tune SNDK            # one ticker
    python run.py tune SNDK NVDA       # subset

Sweeps thresholds + exits + side + entry_type. Splits each ticker's history
70/30 (train/test) by date. Reports top combos by test expectancy AND a
cluster summary so we can tell robust regions from lucky points.
"""
import itertools
from collections import Counter
from dataclasses import replace

import pandas as pd
from tabulate import tabulate

import config
from backtest import simulate_signals
from data_fetcher import fetch_intraday
from signals import apply_signal_rules, attach_indicators
from strategy import ENTRY_TYPES, Strategy

GRID = {
    "entry_type":        list(ENTRY_TYPES),
    "rsi_oversold":      [25, 35, 45, 55],
    "rsi_overbought":    [45, 55, 65, 75],
    "macd_confirm_bars": [1, 2],
    "profit_target":     [0.30, 0.50, 1.00, 2.00],
    "stop_loss":         [-0.40, -0.60],
    "side":              ["calls", "puts", "both"],
}

MIN_TRAIN_TRADES = 15
MIN_TEST_TRADES = 5
TRAIN_FRACTION = 0.70


def _split_by_date(df: pd.DataFrame, frac: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(set(df.index.date))
    if len(dates) < 4:
        return df, df.iloc[0:0]
    cut = dates[int(len(dates) * frac)]
    train = df[df.index.date < cut]
    test = df[df.index.date >= cut]
    return train, test


def _stats(trades) -> dict:
    if not trades:
        return {"n": 0, "win_rate": 0.0, "avg": 0.0, "median": 0.0, "total": 0.0}
    pnls = [t.pnl_pct * 100 for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    return {
        "n": len(pnls),
        "win_rate": wins / len(pnls) * 100,
        "avg": sum(pnls) / len(pnls),
        "median": sorted(pnls)[len(pnls) // 2],
        "total": sum(pnls),
    }


def _evaluate(s: Strategy, train_data: dict, test_data: dict) -> dict:
    train_trades, test_trades = [], []
    for ticker, ind in train_data.items():
        train_trades.extend(simulate_signals(ticker, apply_signal_rules(ind, s), s))
    for ticker, ind in test_data.items():
        test_trades.extend(simulate_signals(ticker, apply_signal_rules(ind, s), s))
    return {"train": _stats(train_trades), "test": _stats(test_trades)}


def _cluster_summary(eligible: pd.DataFrame, top_n: int = 30) -> None:
    """For the top-N combos by test_avg, count how often each parameter value appears.
    Robust edge: top combos cluster around shared values. Lucky peaks: scattered."""
    if len(eligible) < top_n:
        top_n = len(eligible)
    top = eligible.sort_values("test_avg", ascending=False).head(top_n)
    print(f"\n=== PARAMETER CLUSTERING in top {top_n} by test_avg ===")
    print("(robust edge = one value dominates; noise = even distribution)")
    for col in ("entry_type", "side", "rsi_oversold", "rsi_overbought",
                "macd_confirm_bars", "profit_target", "stop_loss"):
        counts = Counter(top[col])
        most = counts.most_common(3)
        line = ", ".join(f"{v}={n}" for v, n in most)
        print(f"  {col:<20} {line}")


def run(tickers: list[str] | None = None) -> None:
    tickers = tickers or config.TICKERS
    print(f"Loading data for {len(tickers)} ticker(s): {', '.join(tickers)}")
    train_data: dict[str, pd.DataFrame] = {}
    test_data: dict[str, pd.DataFrame] = {}
    base = Strategy()
    for ticker in tickers:
        bars = fetch_intraday(ticker, config.BACKTEST_BAR_INTERVAL, config.BACKTEST_LOOKBACK_DAYS)
        if bars.empty:
            print(f"  {ticker}: no data")
            continue
        with_ind = attach_indicators(bars, base)
        train, test = _split_by_date(with_ind, TRAIN_FRACTION)
        train_data[ticker] = train
        test_data[ticker] = test
    print(f"Train days={len({d.date() for df in train_data.values() for d in df.index})}, "
          f"test days={len({d.date() for df in test_data.values() for d in df.index})}")

    keys = list(GRID.keys())
    combos = list(itertools.product(*GRID.values()))
    print(f"Sweeping {len(combos)} combinations across {len(ENTRY_TYPES)} entry types...\n")

    rows = []
    for i, values in enumerate(combos):
        params = dict(zip(keys, values))
        s = replace(base, **params)
        result = _evaluate(s, train_data, test_data)
        rows.append({
            "entry_type": s.entry_type,
            "side": s.side,
            "rsi_oversold": s.rsi_oversold,
            "rsi_overbought": s.rsi_overbought,
            "macd_confirm_bars": s.macd_confirm_bars,
            "profit_target": s.profit_target,
            "stop_loss": s.stop_loss,
            "train_n": result["train"]["n"],
            "train_wr": round(result["train"]["win_rate"], 1),
            "train_avg": round(result["train"]["avg"], 2),
            "test_n": result["test"]["n"],
            "test_wr": round(result["test"]["win_rate"], 1),
            "test_avg": round(result["test"]["avg"], 2),
        })
        if (i + 1) % 200 == 0:
            print(f"  ...{i + 1}/{len(combos)}")

    df = pd.DataFrame(rows)
    eligible = df[(df["train_n"] >= MIN_TRAIN_TRADES) & (df["test_n"] >= MIN_TEST_TRADES)].copy()

    print(f"\nResults: {len(df)} combos evaluated, "
          f"{len(eligible)} with >={MIN_TRAIN_TRADES} train and >={MIN_TEST_TRADES} test trades")

    if eligible.empty:
        print("\nNo combo had enough trades on both halves. Try a smaller MIN_*_TRADES "
              "or a longer history.")
        # show what came closest
        close = df[df["train_n"] >= 5].sort_values("test_avg", ascending=False).head(10)
        if not close.empty:
            print("\nFor reference, top 10 combos with at least 5 train trades:")
            print(tabulate(close, headers="keys", tablefmt="simple", showindex=False))
        return

    print("\n=== TOP 15 BY TEST EXPECTANCY (out-of-sample) ===")
    top_test = eligible.sort_values("test_avg", ascending=False).head(15)
    print(tabulate(top_test, headers="keys", tablefmt="simple", showindex=False))

    print("\n=== ROBUST: positive on BOTH train and test, sorted by test_avg ===")
    robust = eligible[(eligible["train_avg"] > 0) & (eligible["test_avg"] > 0)]
    if robust.empty:
        print("(none — no parameter combo was profitable on both halves)")
    else:
        print(tabulate(robust.sort_values("test_avg", ascending=False).head(15),
                       headers="keys", tablefmt="simple", showindex=False))

    _cluster_summary(eligible, top_n=30)

    print("\n=== BREAKDOWN BY ENTRY TYPE ===")
    by_type = eligible.groupby("entry_type").agg(
        n_combos=("test_avg", "count"),
        avg_test=("test_avg", "mean"),
        best_test=("test_avg", "max"),
        n_profitable=("test_avg", lambda s: (s > 0).sum()),
    ).round(2)
    print(tabulate(by_type, headers="keys", tablefmt="simple"))


if __name__ == "__main__":
    import sys
    run(sys.argv[1:] if len(sys.argv) > 1 else None)
