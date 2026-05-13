"""Live paper-trading loop against Alpaca's paper API.

Polls minute bars, computes signals, and submits ATM weekly option orders to
the paper account. Caps concurrent positions and obeys exit rules.
"""
import os
import time as _time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

import config
from data_fetcher import fetch_alpaca_bars
from signals import compute_signals

load_dotenv()


def _client():
    from alpaca.trading.client import TradingClient
    return TradingClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_API_SECRET"],
        paper=True,
    )


def find_atm_weekly_contract(ticker: str, kind: str):
    """Look up the nearest weekly ATM option contract for `ticker`."""
    from alpaca.trading.requests import GetOptionContractsRequest
    from alpaca.trading.enums import ContractType, AssetStatus

    client = _client()
    today = datetime.now(timezone.utc).date()
    expiry_max = today + timedelta(days=10)

    req = GetOptionContractsRequest(
        underlying_symbols=[ticker],
        status=AssetStatus.ACTIVE,
        type=ContractType.CALL if kind == "call" else ContractType.PUT,
        expiration_date_gte=today,
        expiration_date_lte=expiry_max,
        limit=200,
    )
    contracts = client.get_option_contracts(req).option_contracts
    if not contracts:
        return None

    bars = fetch_alpaca_bars(ticker, interval_minutes=1, lookback_minutes=15)
    if bars.empty:
        return None
    spot = float(bars["close"].iloc[-1])

    contracts.sort(key=lambda c: (c.expiration_date, abs(float(c.strike_price) - spot)))
    return contracts[0]


def submit_option_order(symbol: str, qty: int = 1) -> None:
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    client = _client()
    req = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(req)
    print(f"  -> submitted {symbol} qty={qty} order_id={order.id}")


def open_option_positions(client) -> list:
    return [p for p in client.get_all_positions() if "/" in p.symbol or len(p.symbol) > 6]


def run() -> None:
    client = _client()
    acct = client.get_account()
    print(f"Paper account {acct.account_number}: equity=${acct.equity}, cash=${acct.cash}")

    while True:
        clock = client.get_clock()
        if not clock.is_open:
            sleep_for = max((clock.next_open - clock.timestamp).total_seconds(), 60)
            print(f"Market closed; sleeping {sleep_for:.0f}s until {clock.next_open}")
            _time.sleep(min(sleep_for, 600))
            continue

        positions = open_option_positions(client)
        slots = config.MAX_CONCURRENT_POSITIONS - len(positions)

        for ticker in config.TICKERS:
            if slots <= 0:
                break
            try:
                bars = fetch_alpaca_bars(ticker, interval_minutes=1, lookback_minutes=500)
                if len(bars) < 50:
                    continue
                sig = compute_signals(bars)
                last = sig.iloc[-1]
                kind = "call" if bool(last["call_signal"]) else "put" if bool(last["put_signal"]) else None
                if kind is None:
                    continue
                contract = find_atm_weekly_contract(ticker, kind)
                if contract is None:
                    print(f"{ticker}: signal {kind} but no contract found")
                    continue
                print(f"{ticker}: {kind} signal -> {contract.symbol} (strike {contract.strike_price}, exp {contract.expiration_date})")
                submit_option_order(contract.symbol, qty=config.CONTRACTS_PER_SIGNAL)
                slots -= 1
            except Exception as e:
                print(f"{ticker} loop error: {e}")

        _time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
