"""Sensitivity sweep for bull put credit spreads.

Sweeps target_delta x width_pct x DTE x profit_target across all 9 tickers
and reports:
  - top combos by aggregate P&L
  - % of combos that are profitable
  - marginal effect of each parameter (one-at-a-time)
  - per-combo robustness (how many of 9 tickers were profitable)

Data is fetched once per ticker and reused across all combos.
"""
import itertools
import math

import pandas as pd
from tabulate import tabulate

import config
from spreads import _daily_bars, backtest_bull_put

GRID = {
    "target_delta":   [0.10, 0.16, 0.25, 0.35],
    "width_pct":      [0.03, 0.05, 0.07],
    "dte":            [14, 21, 30, 45],
    "profit_target":  [0.25, 0.50, 0.75],
}


def _eval_combo(params: dict, data_cache: dict, iv_haircut: float = 1.0) -> dict:
    all_trades = []
    profitable_tickers = 0
    n_eligible_tickers = 0
    for ticker, df in data_cache.items():
        trades = backtest_bull_put(
            ticker, dte=params["dte"], target_delta=params["target_delta"],
            width_pct=params["width_pct"], profit_target_frac=params["profit_target"],
            iv_haircut=iv_haircut, bars=df,
        )
        if not trades:
            continue
        n_eligible_tickers += 1
        all_trades.extend(trades)
        if sum(t.pnl for t in trades) > 0:
            profitable_tickers += 1

    if not all_trades:
        return {**params, "n": 0, "tot_pnl": 0.0, "win_rate": 0.0, "avg_roi": 0.0,
                "worst": 0.0, "tickers_won": 0, "tickers_total": 0}

    pnls = [t.pnl for t in all_trades]
    wins = sum(1 for p in pnls if p > 0)
    return {
        **params,
        "n": len(pnls),
        "tot_pnl": round(sum(pnls), 2),
        "win_rate": round(wins / len(pnls) * 100, 1),
        "avg_roi": round(sum(t.roi_on_max_loss for t in all_trades) / len(all_trades) * 100, 2),
        "worst": round(min(pnls), 2),
        "tickers_won": profitable_tickers,
        "tickers_total": n_eligible_tickers,
    }


def _marginal_effect(df: pd.DataFrame, param: str) -> pd.DataFrame:
    return df.groupby(param).agg(
        n_combos=("tot_pnl", "count"),
        avg_total_pnl=("tot_pnl", "mean"),
        median_total_pnl=("tot_pnl", "median"),
        pct_profitable=("tot_pnl", lambda s: (s > 0).mean() * 100),
        avg_roi=("avg_roi", "mean"),
    ).round(2)


def run(tickers: list[str] | None = None, iv_haircut: float | None = None) -> None:
    tickers = tickers or config.SPREAD_TICKERS
    if iv_haircut is None:
        iv_haircut = config.SPREAD_IV_HAIRCUT
    print(f"Caching daily bars for {len(tickers)} tickers (iv_haircut={iv_haircut})...")
    data_cache = {}
    for ticker in tickers:
        df = _daily_bars(ticker, days=365)
        if not df.empty and len(df) >= 60:
            data_cache[ticker] = df
            print(f"  {ticker}: {len(df)} days")
        else:
            print(f"  {ticker}: insufficient data, skipped")
    if not data_cache:
        print("No usable data."); return

    keys = list(GRID.keys())
    combos = list(itertools.product(*GRID.values()))
    print(f"\nSweeping {len(combos)} parameter combinations across {len(data_cache)} tickers...")

    rows = []
    for i, vals in enumerate(combos):
        params = dict(zip(keys, vals))
        rows.append(_eval_combo(params, data_cache, iv_haircut=iv_haircut))
        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{len(combos)}")

    df = pd.DataFrame(rows)

    print("\n" + "=" * 90)
    print("OVERALL")
    print("=" * 90)
    print(f"Combos evaluated: {len(df)}")
    print(f"Combos with positive total P&L: {(df['tot_pnl'] > 0).sum()} "
          f"({(df['tot_pnl'] > 0).mean() * 100:.1f}%)")
    print(f"Combos profitable on >= 8/9 tickers: "
          f"{(df['tickers_won'] >= 8).sum()} ({(df['tickers_won'] >= 8).mean() * 100:.1f}%)")
    print(f"Total P&L range: ${df['tot_pnl'].min():.2f} to ${df['tot_pnl'].max():.2f}")

    print("\n" + "=" * 90)
    print("TOP 15 COMBOS BY TOTAL P&L")
    print("=" * 90)
    cols = ["target_delta", "width_pct", "dte", "profit_target",
            "n", "tot_pnl", "win_rate", "avg_roi", "worst", "tickers_won"]
    print(tabulate(df.sort_values("tot_pnl", ascending=False).head(15)[cols],
                   headers="keys", tablefmt="simple", showindex=False))

    print("\n" + "=" * 90)
    print("MOST ROBUST COMBOS (profitable on all 9 tickers, sorted by tot_pnl)")
    print("=" * 90)
    robust = df[df["tickers_won"] == df["tickers_total"]].sort_values("tot_pnl", ascending=False)
    if robust.empty:
        print("(none — no combo was profitable on every single ticker)")
    else:
        print(tabulate(robust.head(15)[cols], headers="keys", tablefmt="simple", showindex=False))

    print("\n" + "=" * 90)
    print("MARGINAL EFFECT BY PARAMETER (one-at-a-time, averaged over others)")
    print("=" * 90)
    for p in ("target_delta", "width_pct", "dte", "profit_target"):
        print(f"\n[{p}]")
        print(tabulate(_marginal_effect(df, p), headers="keys", tablefmt="simple"))

    print("\n" + "=" * 90)
    print("WORST COMBO")
    print("=" * 90)
    worst = df.sort_values("tot_pnl").head(5)
    print(tabulate(worst[cols], headers="keys", tablefmt="simple", showindex=False))


if __name__ == "__main__":
    run()
