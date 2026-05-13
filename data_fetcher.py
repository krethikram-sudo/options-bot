"""Bar data sources.

- yfinance: free, no key, ~60-day intraday history. Used for backtest/tune/historical-alerts.
- Alpaca:   real-time IEX feed (free tier). Used for the live alert loop.
"""
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf


def fetch_intraday(ticker: str, interval: str = "5m", lookback_days: int = 59) -> pd.DataFrame:
    """yfinance intraday bars. <1h intervals are capped to ~60 days of history."""
    df = yf.download(
        ticker,
        period=f"{lookback_days}d",
        interval=interval,
        auto_adjust=False,
        progress=False,
    )
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    return df.rename(columns=str.lower)


def _alpaca_data_client():
    from alpaca.data.historical import StockHistoricalDataClient

    api_key = os.environ.get("ALPACA_API_KEY")
    api_secret = os.environ.get("ALPACA_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError(
            "ALPACA_API_KEY/ALPACA_API_SECRET not set.\n"
            "  1. Sign up for a free paper account at https://alpaca.markets\n"
            "  2. Generate paper API keys in the dashboard\n"
            "  3. Copy .env.example to .env and paste in your keys"
        )
    return StockHistoricalDataClient(api_key, api_secret)


def fetch_alpaca_bars(ticker: str, interval_minutes: int = 5, lookback_minutes: int = 2880) -> pd.DataFrame:
    """Real-time IEX bars via Alpaca. Default lookback ~2 trading days,
    enough for stable RSI(14) and MACD(26,9) on 5-min bars.
    """
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    client = _alpaca_data_client()
    req = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame(interval_minutes, TimeFrameUnit.Minute),
        start=datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes),
        feed=DataFeed.IEX,
    )
    df = client.get_stock_bars(req).df
    if df.empty:
        return df
    df = df.reset_index()
    df = df.drop(columns=[c for c in ("symbol",) if c in df.columns])
    df = df.set_index("timestamp")
    return df[["open", "high", "low", "close", "volume"]]
