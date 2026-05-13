"""Extended dataset: 6+ years (2020-01 → today) for bear-market testing.

Saves to research/data_extended/ to coexist with the 2-year research/data/.
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

# reuse universe from the original build script
from research.build_dataset import UNIVERSE, _flat_universe, _category_lookup

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data_extended"
PER_TICKER_DIR = DATA_DIR / "tickers"


def fetch_daily(ticker: str, start: str) -> pd.DataFrame:
    try:
        df = yf.download(ticker, start=start, interval="1d",
                         auto_adjust=True, progress=False, threads=False)
        if df.empty:
            return df
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.index.name = "date"
        keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
        return df[keep]
    except Exception as e:
        print(f"  ! {ticker}: {e}")
        return pd.DataFrame()


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PER_TICKER_DIR.mkdir(parents=True, exist_ok=True)

    tickers = _flat_universe()
    cat_lookup = _category_lookup()
    start = "2020-01-01"
    print(f"Extended dataset: {len(tickers)} tickers from {start}")

    per_ticker = {}
    failures = []
    for i, t in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {t} ", end="", flush=True)
        df = fetch_daily(t, start)
        if df.empty:
            print("NO DATA"); failures.append(t); continue
        per_ticker[t] = df
        out = PER_TICKER_DIR / f"{t.replace('^', '_idx_')}.parquet"
        df.to_parquet(out)
        years = (df.index.max() - df.index.min()).days / 365.25
        print(f"{len(df)} rows  ({years:.1f}y)")

    closes = pd.DataFrame({t: df["close"] for t, df in per_ticker.items() if not df.empty})
    closes.to_parquet(DATA_DIR / "closes.parquet")
    closes.pct_change().dropna(how="all").to_parquet(DATA_DIR / "returns.parquet")
    print(f"Saved closes.parquet: {closes.shape[0]} dates × {closes.shape[1]} tickers")

    metadata = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start_date": start, "n_tickers": len(per_ticker),
        "tickers": sorted(per_ticker.keys()),
        "failures": failures,
        "universe_categories": UNIVERSE,
        "category_by_ticker": cat_lookup,
    }
    with (DATA_DIR / "metadata.json").open("w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata.json")


if __name__ == "__main__":
    main()
