"""Post-earnings-announcement drift (PEAD) backtest.

Academic finding (Bernard & Thomas 1989): stocks that beat earnings drift
upward over the following weeks; stocks that miss drift downward.

Test on our 138-ticker universe:
  - Buy at close on T+1 after a positive earnings surprise (>X%)
  - Sell at close after N days
  - Compare to: buying after a negative surprise (or random dates)

Tests multiple holding periods (1, 3, 5, 10, 21, 42 days) and surprise
thresholds (0%, 5%, 10%, 20%) to characterize the drift.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf
from tabulate import tabulate

from research.data_lib import all_tickers, load_closes


@dataclass
class EarningsEvent:
    ticker: str
    earnings_date: pd.Timestamp
    surprise_pct: float
    eps_estimate: float
    reported_eps: float


def fetch_earnings_events(tickers: list[str], lookback_days: int = 730) -> list[EarningsEvent]:
    """Pull historical earnings data via yfinance."""
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
    out: list[EarningsEvent] = []
    for t in tickers:
        try:
            ed = yf.Ticker(t).earnings_dates
        except Exception:
            continue
        if ed is None or ed.empty:
            continue
        # past earnings only (have reported EPS)
        if "Reported EPS" not in ed.columns:
            continue
        past = ed[ed["Reported EPS"].notna()]
        if past.empty:
            continue
        # filter to lookback window
        idx = past.index.tz_localize(None) if past.index.tz is not None else past.index
        past = past[idx >= cutoff]
        if past.empty:
            continue
        for ts, row in past.iterrows():
            try:
                surprise = row.get("Surprise(%)", None)
                eps_est = row.get("EPS Estimate", None)
                eps_rep = row.get("Reported EPS", None)
                if pd.isna(surprise) or pd.isna(eps_est) or pd.isna(eps_rep):
                    continue
                ts_naive = ts.tz_localize(None) if ts.tz is not None else ts
                out.append(EarningsEvent(
                    ticker=t, earnings_date=ts_naive,
                    surprise_pct=float(surprise),
                    eps_estimate=float(eps_est),
                    reported_eps=float(eps_rep),
                ))
            except Exception:
                continue
    return out


def find_trading_day_offset(closes: pd.DataFrame, target: pd.Timestamp,
                             days_offset: int) -> pd.Timestamp | None:
    """Find the trading-day at offset days_offset from target (T+N or T-N)."""
    target_d = target.normalize()
    if days_offset >= 0:
        # smallest trading day >= target, then advance by days_offset more trading days
        future = closes.index[closes.index >= target_d]
        if len(future) <= days_offset:
            return None
        return future[days_offset]
    else:
        past = closes.index[closes.index <= target_d]
        if len(past) <= abs(days_offset):
            return None
        return past[days_offset]  # python negative indexing


def event_study(
    events: list[EarningsEvent],
    closes: pd.DataFrame,
    surprise_threshold_pct: float,
    holding_days: int,
    direction: str = "positive",  # "positive" | "negative"
) -> dict:
    """Compute mean/median forward return for events meeting the threshold."""
    returns = []
    trades = []
    for ev in events:
        s = ev.surprise_pct
        if direction == "positive" and s < surprise_threshold_pct:
            continue
        if direction == "negative" and s > -surprise_threshold_pct:
            continue
        if ev.ticker not in closes.columns:
            continue

        entry_dt = find_trading_day_offset(closes, ev.earnings_date, days_offset=1)
        if entry_dt is None:
            continue
        exit_dt = find_trading_day_offset(closes, entry_dt, days_offset=holding_days)
        if exit_dt is None:
            continue

        try:
            entry_px = float(closes.loc[entry_dt, ev.ticker])
            exit_px = float(closes.loc[exit_dt, ev.ticker])
        except KeyError:
            continue
        if pd.isna(entry_px) or pd.isna(exit_px) or entry_px <= 0:
            continue
        ret = (exit_px - entry_px) / entry_px
        returns.append(ret)
        trades.append({
            "ticker": ev.ticker,
            "earnings_date": ev.earnings_date.date().isoformat(),
            "surprise_pct": ev.surprise_pct,
            "entry_date": entry_dt.date().isoformat(),
            "exit_date": exit_dt.date().isoformat(),
            "entry_px": entry_px, "exit_px": exit_px,
            "ret": ret,
        })

    if not returns:
        return {"n": 0}
    arr = np.array(returns)
    return {
        "n": len(arr),
        "mean_ret": float(arr.mean()),
        "median_ret": float(np.median(arr)),
        "win_rate": float((arr > 0).mean()),
        "std_ret": float(arr.std()),
        "min_ret": float(arr.min()),
        "max_ret": float(arr.max()),
        "cumulative": float(np.prod(1 + arr) - 1),  # if you'd done all of them
        "sharpe_per_event": float(arr.mean() / arr.std()) if arr.std() > 0 else 0,
    }


def run_pead_grid(events: list[EarningsEvent], closes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for direction in ["positive", "negative"]:
        for thresh in [0, 5, 10, 20]:
            for hold in [1, 3, 5, 10, 21, 42]:
                stats = event_study(events, closes, surprise_threshold_pct=thresh,
                                    holding_days=hold, direction=direction)
                if stats["n"] == 0:
                    continue
                rows.append({
                    "direction": direction,
                    "thresh_pct": thresh,
                    "hold_days": hold,
                    **stats,
                })
    return pd.DataFrame(rows)


def main():
    closes = load_closes()
    tickers = list(closes.columns)
    print(f"Fetching earnings data for {len(tickers)} tickers...")
    events = fetch_earnings_events(tickers)
    print(f"Got {len(events)} earnings events with surprise data")
    if not events:
        print("No earnings data — aborting")
        return

    # quick stats on universe
    print()
    print("=== EVENT DISTRIBUTION ===")
    surprises = [e.surprise_pct for e in events]
    print(f"  surprise_pct mean: {np.mean(surprises):.2f}%")
    print(f"  surprise_pct median: {np.median(surprises):.2f}%")
    print(f"  positive surprises: {sum(1 for s in surprises if s > 0)} ({sum(1 for s in surprises if s > 0)/len(surprises)*100:.0f}%)")
    print(f"  big positive (>10%): {sum(1 for s in surprises if s > 10)}")
    print(f"  big negative (<-10%): {sum(1 for s in surprises if s < -10)}")

    print()
    print("=== PEAD EVENT STUDY ===")
    df = run_pead_grid(events, closes)
    if df.empty:
        print("no eligible events")
        return

    # format mean_ret as percent
    df["mean_ret_pct"] = (df["mean_ret"] * 100).round(2)
    df["median_ret_pct"] = (df["median_ret"] * 100).round(2)
    df["win_rate_pct"] = (df["win_rate"] * 100).round(0)
    df["std_ret_pct"] = (df["std_ret"] * 100).round(2)

    show = df[["direction", "thresh_pct", "hold_days", "n",
               "mean_ret_pct", "median_ret_pct", "win_rate_pct",
               "std_ret_pct", "sharpe_per_event"]].sort_values(
        ["direction", "thresh_pct", "hold_days"])
    print(tabulate(show, headers="keys", tablefmt="simple", showindex=False))

    from pathlib import Path
    out = Path(__file__).resolve().parent / "earnings_drift_results.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")

    # summary of best setups
    print()
    print("=== TOP 5 SETUPS BY SHARPE (per-event) ===")
    top = df.sort_values("sharpe_per_event", ascending=False).head(5)
    print(tabulate(top[["direction", "thresh_pct", "hold_days", "n",
                        "mean_ret_pct", "win_rate_pct", "sharpe_per_event"]],
                   headers="keys", tablefmt="simple", showindex=False))


if __name__ == "__main__":
    main()
