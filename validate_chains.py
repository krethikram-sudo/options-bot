"""Validate the bull-put-spread strategy against real Alpaca option chains.

For each ticker, finds the actual contract that matches our strategy (closest
to 25-delta put, ~14 DTE, with a long put 5% lower) and compares:
  - Real implied vol  vs  our 30-day realized vol assumption
  - Real chain credit (mid + conservative)  vs  Black-Scholes-synthesized credit

A material gap means our backtest results need haircut. A small gap means
the BS model is honest enough that the +576% annualized headline is real-ish.

Note: market was last open Friday. Quotes will reflect that close.
"""
import math
import os
import sys
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from tabulate import tabulate

import config
from black_scholes import bs_delta, bs_price

load_dotenv()
RATE = 0.045
TARGET_DELTA = 0.25
WIDTH_PCT = 0.05
TARGET_DTE = 14


def _trading_client():
    from alpaca.trading.client import TradingClient
    return TradingClient(os.environ["ALPACA_API_KEY"],
                         os.environ["ALPACA_API_SECRET"], paper=True)


def _option_data_client():
    from alpaca.data.historical.option import OptionHistoricalDataClient
    return OptionHistoricalDataClient(os.environ["ALPACA_API_KEY"],
                                      os.environ["ALPACA_API_SECRET"])


def _stock_data_client():
    from alpaca.data.historical.stock import StockHistoricalDataClient
    return StockHistoricalDataClient(os.environ["ALPACA_API_KEY"],
                                     os.environ["ALPACA_API_SECRET"])


def get_spot(ticker: str) -> float:
    from alpaca.data.requests import StockLatestQuoteRequest
    client = _stock_data_client()
    q = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=ticker))[ticker]
    if q.ask_price and q.bid_price:
        return (q.bid_price + q.ask_price) / 2
    return q.ask_price or q.bid_price


def realized_vol(ticker: str, window: int = 30) -> float:
    df = yf.download(ticker, period="90d", interval="1d", auto_adjust=False, progress=False)
    if df.empty:
        return 0.50
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    closes = df["Close"]
    log_ret = (closes / closes.shift(1)).apply(lambda x: math.log(x) if x and x > 0 else None).dropna()
    return float(log_ret.tail(window).std() * math.sqrt(252))


def find_target_expiry_chain(ticker: str, target_dte: int) -> tuple[date | None, list]:
    from alpaca.trading.enums import AssetStatus, ContractType
    from alpaca.trading.requests import GetOptionContractsRequest

    today = date.today()
    target = today + timedelta(days=target_dte)
    client = _trading_client()
    req = GetOptionContractsRequest(
        underlying_symbols=[ticker],
        type=ContractType.PUT,
        status=AssetStatus.ACTIVE,
        expiration_date_gte=today + timedelta(days=max(target_dte - 7, 1)),
        expiration_date_lte=today + timedelta(days=target_dte + 14),
        limit=1000,
    )
    contracts = client.get_option_contracts(req).option_contracts
    if not contracts:
        return None, []
    expirations = sorted({c.expiration_date for c in contracts})
    expiry = min(expirations, key=lambda e: abs((e - target).days))
    chain = sorted([c for c in contracts if c.expiration_date == expiry],
                   key=lambda c: float(c.strike_price))
    return expiry, chain


def get_chain_snapshots(symbols: list[str]) -> dict:
    from alpaca.data.requests import OptionLatestQuoteRequest
    if not symbols:
        return {}
    client = _option_data_client()
    # latest_quote works on free tier; full snapshot/greeks may not
    quotes = client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=symbols))
    return quotes


def compare_ticker(ticker: str) -> dict | None:
    try:
        spot = get_spot(ticker)
    except Exception as e:
        print(f"  {ticker}: spot fetch failed — {e}")
        return None

    expiry, chain = find_target_expiry_chain(ticker, TARGET_DTE)
    if not chain:
        print(f"  {ticker}: no put chain near {TARGET_DTE} DTE")
        return None
    actual_dte = (expiry - date.today()).days
    if actual_dte <= 0:
        print(f"  {ticker}: expiry {expiry} is past")
        return None

    rv = realized_vol(ticker)
    t_years = actual_dte / 365.0

    # find short put: closest to target delta using BS-computed delta on each strike
    candidates = []
    for c in chain:
        strike = float(c.strike_price)
        if strike <= 0:
            continue
        d = bs_delta(spot, strike, t_years, RATE, rv, "put")
        candidates.append((c, strike, d))

    if not candidates:
        print(f"  {ticker}: no candidates")
        return None

    # short = put with delta closest to -TARGET_DELTA
    short_c, short_strike, short_delta = min(candidates, key=lambda x: abs(x[2] + TARGET_DELTA))
    target_long_strike = short_strike - max(spot * WIDTH_PCT, 1.0)
    long_c, long_strike, long_delta = min(candidates, key=lambda x: abs(x[1] - target_long_strike))

    # quotes for both legs
    quotes = get_chain_snapshots([short_c.symbol, long_c.symbol])
    sq = quotes.get(short_c.symbol)
    lq = quotes.get(long_c.symbol)
    if not sq or not lq:
        print(f"  {ticker}: missing quote(s)")
        return None

    short_bid, short_ask = float(sq.bid_price or 0), float(sq.ask_price or 0)
    long_bid, long_ask = float(lq.bid_price or 0), float(lq.ask_price or 0)
    short_mid = (short_bid + short_ask) / 2
    long_mid = (long_bid + long_ask) / 2

    real_credit_mid = short_mid - long_mid
    real_credit_conservative = short_bid - long_ask  # sell at bid, buy at ask

    bs_short = bs_price(spot, short_strike, t_years, RATE, rv, "put")
    bs_long = bs_price(spot, long_strike, t_years, RATE, rv, "put")
    bs_credit = bs_short - bs_long

    width = short_strike - long_strike

    return {
        "ticker": ticker,
        "spot": round(spot, 2),
        "dte": actual_dte,
        "short_strike": short_strike,
        "short_delta": round(short_delta, 3),
        "long_strike": long_strike,
        "width": round(width, 2),
        "rv_30d": round(rv * 100, 1),
        "real_mid": round(real_credit_mid, 2),
        "real_market": round(real_credit_conservative, 2),
        "bs_credit": round(bs_credit, 2),
        "overstatement_vs_mid_pct": round((bs_credit / real_credit_mid - 1) * 100, 1) if real_credit_mid > 0 else None,
        "overstatement_vs_market_pct": round((bs_credit / real_credit_conservative - 1) * 100, 1) if real_credit_conservative > 0 else None,
        "short_bid_ask": f"{short_bid:.2f}/{short_ask:.2f}",
        "long_bid_ask": f"{long_bid:.2f}/{long_ask:.2f}",
    }


def run(tickers: list[str] | None = None) -> None:
    tickers = tickers or config.TICKERS
    print(f"Validating bull put spreads against real Alpaca chains")
    print(f"  Target: short put at delta ~{TARGET_DELTA}, long {WIDTH_PCT*100:.0f}% lower, {TARGET_DTE} DTE")
    print()

    rows = []
    for t in tickers:
        print(f"  fetching {t}...")
        try:
            r = compare_ticker(t)
        except Exception as e:
            print(f"    error: {e}")
            continue
        if r:
            rows.append(r)

    if not rows:
        print("\nNo successful comparisons.")
        return

    df = pd.DataFrame(rows)
    print("\n" + "=" * 100)
    print("CHAIN COMPARISON")
    print("=" * 100)
    cols = ["ticker", "spot", "dte", "short_strike", "short_delta", "long_strike", "width",
            "rv_30d", "real_mid", "real_market", "bs_credit",
            "overstatement_vs_mid_pct", "overstatement_vs_market_pct"]
    print(tabulate(df[cols], headers="keys", tablefmt="simple", showindex=False))

    print("\n" + "=" * 100)
    print("CALIBRATION")
    print("=" * 100)
    valid = df.dropna(subset=["overstatement_vs_mid_pct"])
    if not valid.empty:
        avg_over_mid = valid["overstatement_vs_mid_pct"].mean()
        med_over_mid = valid["overstatement_vs_mid_pct"].median()
        avg_over_market = valid["overstatement_vs_market_pct"].mean()
        med_over_market = valid["overstatement_vs_market_pct"].median()
        print(f"  Mean overstatement (BS vs real mid):       {avg_over_mid:+.1f}%")
        print(f"  Median overstatement (BS vs real mid):     {med_over_mid:+.1f}%")
        print(f"  Mean overstatement (BS vs conservative):   {avg_over_market:+.1f}%")
        print(f"  Median overstatement (BS vs conservative): {med_over_market:+.1f}%")
        print()
        if abs(med_over_mid) < 10:
            print("  Verdict: BS model close to real chains. Backtest credibility HIGH.")
        elif med_over_mid > 25:
            print("  Verdict: BS model materially OVERSTATES credits. Real returns will be much smaller.")
        elif med_over_mid < -25:
            print("  Verdict: BS UNDERstates credits. Real returns may be even larger than backtest!")
        else:
            print("  Verdict: BS model has modest gap. Apply haircut to backtest expectations.")


if __name__ == "__main__":
    run(sys.argv[1:] if len(sys.argv) > 1 else None)
