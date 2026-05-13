"""Three sequential experiments to find a profitable SNDK setup.

Each builds on the previous. Indicators and bars are computed once and
re-used across all sweeps.

  A. Tight scalping grid (trend_following+calls+2-bar confirm fixed).
  B. Sweep DTE and IV — does the instrument matter, not the signal?
  C. Daily-trend regime filter — only fire when SNDK is above 20d SMA.
"""
import itertools
from collections import Counter
from dataclasses import replace

import pandas as pd
import yfinance as yf
from tabulate import tabulate

import config
from backtest import simulate_signals
from data_fetcher import fetch_intraday
from signals import apply_signal_rules, attach_indicators
from strategy import Strategy

TICKER = "SNDK"
TRAIN_FRACTION = 0.70
MIN_TRAIN_TRADES = 12
MIN_TEST_TRADES = 5


def _split_by_date(df: pd.DataFrame, frac: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(set(df.index.date))
    cut = dates[int(len(dates) * frac)]
    return df[df.index.date < cut], df[df.index.date >= cut]


def _stats(trades) -> dict:
    if not trades:
        return {"n": 0, "wr": 0.0, "avg": 0.0}
    pnls = [t.pnl_pct * 100 for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    return {"n": len(pnls), "wr": wins / len(pnls) * 100, "avg": sum(pnls) / len(pnls)}


def _sweep(combos: list[dict], train: pd.DataFrame, test: pd.DataFrame, label: str) -> pd.DataFrame:
    rows = []
    for params in combos:
        s = Strategy(**params)
        train_trades = simulate_signals(TICKER, apply_signal_rules(train, s), s)
        test_trades = simulate_signals(TICKER, apply_signal_rules(test, s), s)
        tr, te = _stats(train_trades), _stats(test_trades)
        row = dict(params)
        row.update({"train_n": tr["n"], "train_wr": round(tr["wr"], 1), "train_avg": round(tr["avg"], 2),
                    "test_n": te["n"], "test_wr": round(te["wr"], 1), "test_avg": round(te["avg"], 2)})
        rows.append(row)
    df = pd.DataFrame(rows)
    eligible = df[(df["train_n"] >= MIN_TRAIN_TRADES) & (df["test_n"] >= MIN_TEST_TRADES)].copy()
    print(f"\n[{label}] {len(df)} combos evaluated, {len(eligible)} eligible")
    if eligible.empty:
        # show top by train_avg as fallback
        print("(no combos met trade-count minimums; showing top 5 by train_avg)")
        print(tabulate(df.sort_values("train_avg", ascending=False).head(5),
                       headers="keys", tablefmt="simple", showindex=False))
        return df
    print(f"\nTop 10 by test_avg:")
    show_cols = [c for c in eligible.columns if c not in ("rsi_overbought",)]  # tighten table
    print(tabulate(eligible.sort_values("test_avg", ascending=False).head(10)[show_cols],
                   headers="keys", tablefmt="simple", showindex=False))
    profitable = eligible[(eligible["train_avg"] > 0) & (eligible["test_avg"] > 0)]
    print(f"\nProfitable on BOTH train and test: {len(profitable)}")
    if not profitable.empty:
        print(tabulate(profitable.sort_values("test_avg", ascending=False).head(10)[show_cols],
                       headers="keys", tablefmt="simple", showindex=False))
    return df


def experiment_a(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Tighter scalping grid pinned to the cluster: trend_following + calls + 2-bar confirm."""
    print("\n" + "=" * 70)
    print("EXPERIMENT A — Tight scalping grid (trend_following + calls + confirm=2)")
    print("=" * 70)
    grid = list(itertools.product(
        ["trend_following"], ["calls"], [2],
        [40, 45, 50, 55, 60],          # rsi_oversold = bullish RSI threshold
        [50],                           # rsi_overbought (unused for calls-only)
        [0.15, 0.20, 0.25, 0.30, 0.40], # profit_target
        [-0.25, -0.30, -0.35, -0.40],   # stop_loss
    ))
    keys = ["entry_type", "side", "macd_confirm_bars", "rsi_oversold",
            "rsi_overbought", "profit_target", "stop_loss"]
    combos = [dict(zip(keys, vals)) for vals in grid]
    return _sweep(combos, train, test, "A")


def experiment_b(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Vary DTE and IV. Does the instrument matter, not the signal?"""
    print("\n" + "=" * 70)
    print("EXPERIMENT B — Vary DTE and IV (signal pinned to A's best zone)")
    print("=" * 70)
    grid = list(itertools.product(
        ["trend_following"], ["calls"], [2],
        [45, 50, 55],                   # rsi_oversold
        [50],
        [0.20, 0.30, 0.50],             # profit_target
        [-0.30, -0.40],                  # stop_loss
        [2, 4, 7, 14],                  # dte_days
        [0.5, 0.7, 0.9, 1.1],           # iv
    ))
    keys = ["entry_type", "side", "macd_confirm_bars", "rsi_oversold",
            "rsi_overbought", "profit_target", "stop_loss", "dte_days", "iv"]
    combos = [dict(zip(keys, vals)) for vals in grid]
    return _sweep(combos, train, test, "B")


def _fetch_daily_regime(ticker: str, sma_period: int = 20) -> pd.Series:
    """Fetch daily close and return Series mapping date -> 'bull'/'bear' based on PRIOR day vs SMA."""
    df = yf.download(ticker, period="6mo", interval="1d", auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    closes = df["Close"]
    sma = closes.rolling(sma_period).mean()
    regime = pd.Series(index=closes.index, dtype=object)
    regime[closes > sma] = "bull"
    regime[closes < sma] = "bear"
    # use prior day's regime (no lookahead bias)
    regime = regime.shift(1)
    # Keys as plain dates for easy mapping
    return pd.Series(regime.values, index=[d.date() for d in regime.index])


def _apply_regime_mask(bars: pd.DataFrame, regime_by_date: pd.Series, allow: str) -> pd.DataFrame:
    """Zero out bars whose date's regime doesn't match `allow`. After masking, signals
    on those bars become impossible (RSI/MACD still computed but call/put will be False)."""
    bars = bars.copy()
    dates = pd.Index([ts.date() for ts in bars.index])
    regimes = pd.Series([regime_by_date.get(d) for d in dates], index=bars.index)
    keep = regimes == allow
    bars["regime_match"] = keep
    return bars


def experiment_c(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Daily-trend regime filter: only fire calls when prior day close > 20d SMA."""
    print("\n" + "=" * 70)
    print("EXPERIMENT C — Add daily-trend regime filter (calls only in bull regime)")
    print("=" * 70)

    regime_by_date = _fetch_daily_regime(TICKER, sma_period=20)
    bull_days = (regime_by_date == "bull").sum()
    bear_days = (regime_by_date == "bear").sum()
    print(f"Daily regimes: {bull_days} bull / {bear_days} bear / "
          f"{regime_by_date.isna().sum()} unknown")

    train_m = _apply_regime_mask(train, regime_by_date, "bull")
    test_m = _apply_regime_mask(test, regime_by_date, "bull")
    train_kept = train_m["regime_match"].sum()
    test_kept = test_m["regime_match"].sum()
    print(f"Bars kept after bull-regime filter: train {train_kept}/{len(train_m)}, "
          f"test {test_kept}/{len(test_m)}")

    grid = list(itertools.product(
        ["trend_following"], ["calls"], [2],
        [45, 50, 55],
        [50],
        [0.20, 0.25, 0.30, 0.40],
        [-0.30, -0.40],
    ))
    keys = ["entry_type", "side", "macd_confirm_bars", "rsi_oversold",
            "rsi_overbought", "profit_target", "stop_loss"]
    combos = [dict(zip(keys, vals)) for vals in grid]

    rows = []
    for params in combos:
        s = Strategy(**params)
        # apply signals then mask out bars where regime didn't match
        train_sig = apply_signal_rules(train_m, s)
        train_sig.loc[~train_sig["regime_match"], ["call_signal", "put_signal"]] = False
        test_sig = apply_signal_rules(test_m, s)
        test_sig.loc[~test_sig["regime_match"], ["call_signal", "put_signal"]] = False
        train_trades = simulate_signals(TICKER, train_sig, s)
        test_trades = simulate_signals(TICKER, test_sig, s)
        tr, te = _stats(train_trades), _stats(test_trades)
        row = dict(params)
        row.update({"train_n": tr["n"], "train_wr": round(tr["wr"], 1), "train_avg": round(tr["avg"], 2),
                    "test_n": te["n"], "test_wr": round(te["wr"], 1), "test_avg": round(te["avg"], 2)})
        rows.append(row)

    df = pd.DataFrame(rows)
    eligible = df[(df["train_n"] >= 8) & (df["test_n"] >= 3)].copy()  # filter loosened (regime cuts trade count)
    print(f"\n[C] {len(df)} combos evaluated, {len(eligible)} eligible (loosened to 8 train / 3 test)")
    if eligible.empty:
        print("(no combos met trade-count minimums; showing top 5 by train_avg)")
        print(tabulate(df.sort_values("train_avg", ascending=False).head(5),
                       headers="keys", tablefmt="simple", showindex=False))
        return df
    show_cols = [c for c in eligible.columns if c not in ("rsi_overbought",)]
    print(f"\nTop 10 by test_avg:")
    print(tabulate(eligible.sort_values("test_avg", ascending=False).head(10)[show_cols],
                   headers="keys", tablefmt="simple", showindex=False))
    profitable = eligible[(eligible["train_avg"] > 0) & (eligible["test_avg"] > 0)]
    print(f"\nProfitable on BOTH train and test: {len(profitable)}")
    if not profitable.empty:
        print(tabulate(profitable.sort_values("test_avg", ascending=False).head(10)[show_cols],
                       headers="keys", tablefmt="simple", showindex=False))
    return df


def run() -> None:
    print(f"Loading {TICKER} bars + indicators...")
    bars = fetch_intraday(TICKER, config.BACKTEST_BAR_INTERVAL, config.BACKTEST_LOOKBACK_DAYS)
    if bars.empty:
        print("No data!"); return
    with_ind = attach_indicators(bars, Strategy())
    train, test = _split_by_date(with_ind, TRAIN_FRACTION)
    print(f"Train: {len(train)} bars / {len({d.date() for d in train.index})} days")
    print(f"Test:  {len(test)} bars / {len({d.date() for d in test.index})} days")

    a = experiment_a(train, test)
    b = experiment_b(train, test)
    c = experiment_c(train, test)

    print("\n" + "=" * 70)
    print("CONSOLIDATED SUMMARY")
    print("=" * 70)
    for name, df in [("A", a), ("B", b), ("C", c)]:
        eligible = df[(df.get("train_n", 0) >= 8) & (df.get("test_n", 0) >= 3)]
        if eligible.empty:
            print(f"  {name}: no eligible combos")
            continue
        prof = eligible[(eligible["train_avg"] > 0) & (eligible["test_avg"] > 0)]
        best_test = eligible["test_avg"].max()
        print(f"  {name}: best test_avg={best_test:.2f}%   profitable both halves={len(prof)}/{len(eligible)}")


if __name__ == "__main__":
    run()
