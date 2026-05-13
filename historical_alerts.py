"""Replay the signal logic on historical bars and list every alert that
WOULD have fired. No simulation of P&L — just the alert log you'd have seen
if you'd been running the live monitor over the period.
"""
import pandas as pd
from tabulate import tabulate

import config
from data_fetcher import fetch_intraday
from signals import compute_signals
from strategy import Strategy


def run() -> None:
    s = Strategy()
    print(f"Strategy: {s.label()}")
    print(f"Replaying {config.BACKTEST_LOOKBACK_DAYS}d of "
          f"{config.BACKTEST_BAR_INTERVAL} bars across {len(config.TICKERS)} tickers...\n")

    rows = []
    for ticker in config.TICKERS:
        bars = fetch_intraday(ticker, config.BACKTEST_BAR_INTERVAL, config.BACKTEST_LOOKBACK_DAYS)
        if bars.empty:
            print(f"  {ticker}: no data")
            continue
        sig = compute_signals(bars, s)
        for ts, row in sig.iterrows():
            is_call = bool(row["call_signal"])
            is_put = bool(row["put_signal"])
            if not (is_call or is_put):
                continue
            rows.append({
                "time": ts.strftime("%Y-%m-%d %H:%M"),
                "ticker": ticker,
                "side": "call" if is_call else "put",
                "spot": round(float(row["close"]), 2),
                "rsi": round(float(row["rsi"]), 1),
                "hist": round(float(row["hist"]), 3),
            })

    if not rows:
        print("No alerts would have fired.")
        return

    df = pd.DataFrame(rows).sort_values("time")
    # show last 30 since output can be long
    show = df.tail(30)
    print(tabulate(show, headers="keys", tablefmt="simple", showindex=False))
    print(f"\n(showing most recent {len(show)} of {len(df)} total alerts)\n")
    print("By ticker:")
    print(df.groupby("ticker").size().to_string())
    print("\nBy side:")
    print(df.groupby("side").size().to_string())


if __name__ == "__main__":
    run()
