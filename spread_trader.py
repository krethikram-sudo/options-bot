"""Auto-executed bull put credit spreads with risk limits.

Two responsibilities:
  - daily_entry_scan(): once per market day, look for new entries on tickers
    that don't already have an open position, subject to global limits.
  - monitor_exits(): every poll cycle, check open spreads for profit-target
    fills and submit closing orders.

State is held in `logs/spread_positions.jsonl` (append-only). Each line is the
most recent known event for a position (open / partial fill / closed). On
startup we replay this file and reconcile against Alpaca's current positions
so we recover cleanly from restarts.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

import config
from alerts import (PRIORITY_DEFAULT, PRIORITY_HIGH, Notifier, ScanSummary,
                    dispatch)
from black_scholes import bs_delta
from validate_chains import (find_target_expiry_chain, get_chain_snapshots,
                             get_spot, realized_vol)

load_dotenv()

STATE_PATH = Path("logs/spread_positions.jsonl")
RATE = 0.045

# Alpaca OCC option symbol format: {UNDERLYING}{YYMMDD}{C|P}{STRIKE*1000:08d}
_OCC_RE = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")


def _trading_client():
    from alpaca.trading.client import TradingClient
    return TradingClient(os.environ["ALPACA_API_KEY"],
                         os.environ["ALPACA_API_SECRET"], paper=True)


def _parse_occ(symbol: str) -> tuple[str, date, str, float] | None:
    m = _OCC_RE.match(symbol)
    if not m:
        return None
    underlying, yymmdd, kind, strike_str = m.groups()
    expiry = date(2000 + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6]))
    strike = int(strike_str) / 1000.0
    return underlying, expiry, kind, strike


# ---------- state ----------

@dataclass
class SpreadPosition:
    ticker: str
    short_symbol: str
    long_symbol: str
    short_strike: float
    long_strike: float
    width: float
    entry_credit: float
    expiry: str            # ISO date
    open_date: str         # ISO datetime
    qty: int
    status: str = "open"   # open | closed | partial
    close_date: str | None = None
    close_debit: float | None = None
    realized_pnl: float | None = None
    open_order_id: str | None = None
    close_order_id: str | None = None

    @property
    def max_loss_per_spread(self) -> float:
        return self.width - self.entry_credit

    @property
    def max_loss_total(self) -> float:
        return self.max_loss_per_spread * self.qty * 100  # 100 shares/contract


def _append_state(pos: SpreadPosition) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("a") as f:
        f.write(json.dumps(asdict(pos)) + "\n")


def load_state() -> dict[str, SpreadPosition]:
    """Replay the JSONL log; latest entry per (short_symbol, long_symbol) wins."""
    if not STATE_PATH.exists():
        return {}
    positions: dict[str, SpreadPosition] = {}
    with STATE_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            key = f"{d['short_symbol']}|{d['long_symbol']}"
            positions[key] = SpreadPosition(**d)
    return positions


def open_positions_from_state() -> list[SpreadPosition]:
    return [p for p in load_state().values() if p.status == "open"]


def reconcile_with_alpaca() -> list[SpreadPosition]:
    """Cross-check local state against Alpaca's actual open option positions.
    Returns the list of locally-tracked positions that Alpaca confirms are still open."""
    local_open = open_positions_from_state()
    if not local_open:
        return []

    client = _trading_client()
    try:
        positions = client.get_all_positions()
    except Exception as e:
        print(f"  [reconcile] failed to fetch Alpaca positions: {e}")
        return local_open  # trust local state

    alpaca_symbols = {p.symbol for p in positions}
    confirmed = []
    for sp in local_open:
        if sp.short_symbol in alpaca_symbols and sp.long_symbol in alpaca_symbols:
            confirmed.append(sp)
        else:
            # we think it's open but Alpaca says no — mark as closed in state
            print(f"  [reconcile] local open spread not found at Alpaca, marking closed: "
                  f"{sp.ticker} {sp.short_symbol}/{sp.long_symbol}")
            sp.status = "closed"
            sp.close_date = datetime.now(timezone.utc).isoformat()
            sp.realized_pnl = None  # unknown
            _append_state(sp)
    return confirmed


# ---------- candidate finding ----------

@dataclass
class SpreadCandidate:
    ticker: str
    short_symbol: str
    long_symbol: str
    short_strike: float
    long_strike: float
    short_delta: float
    short_mid: float
    long_mid: float
    expected_credit: float
    width: float
    expiry: date
    dte: int
    spot: float

    @property
    def max_loss_per_spread(self) -> float:
        return self.width - self.expected_credit


def find_bull_put_candidate(ticker: str) -> SpreadCandidate | None:
    try:
        spot = get_spot(ticker)
    except Exception as e:
        print(f"  [{ticker}] spot fetch failed: {e}")
        return None

    expiry, chain = find_target_expiry_chain(ticker, target_dte=config.SPREAD_DTE)
    if not chain:
        return None
    actual_dte = (expiry - date.today()).days
    if actual_dte <= 5:
        return None

    rv_calibrated = realized_vol(ticker) * config.SPREAD_IV_HAIRCUT
    t_years = actual_dte / 365.0

    candidates = []
    for c in chain:
        strike = float(c.strike_price)
        if strike <= 0:
            continue
        delta = bs_delta(spot, strike, t_years, RATE, rv_calibrated, "put")
        candidates.append((c, strike, delta))
    if not candidates:
        return None

    short_c, short_strike, short_delta = min(
        candidates, key=lambda x: abs(x[2] + config.SPREAD_TARGET_DELTA)
    )
    target_long = short_strike - max(spot * config.SPREAD_WIDTH_PCT, 1.0)
    long_c, long_strike, _ = min(candidates, key=lambda x: abs(x[1] - target_long))
    if long_strike >= short_strike:
        return None

    # real-time quotes
    quotes = get_chain_snapshots([short_c.symbol, long_c.symbol])
    sq = quotes.get(short_c.symbol)
    lq = quotes.get(long_c.symbol)
    if not sq or not lq:
        return None

    short_bid, short_ask = float(sq.bid_price or 0), float(sq.ask_price or 0)
    long_bid, long_ask = float(lq.bid_price or 0), float(lq.ask_price or 0)
    if short_bid == 0 or short_ask == 0 or long_ask == 0:
        return None

    short_mid = (short_bid + short_ask) / 2
    long_mid = (long_bid + long_ask) / 2
    expected_credit = short_mid - long_mid
    if expected_credit < config.SPREAD_MIN_CREDIT:
        return None

    return SpreadCandidate(
        ticker=ticker,
        short_symbol=short_c.symbol, long_symbol=long_c.symbol,
        short_strike=short_strike, long_strike=long_strike,
        short_delta=short_delta,
        short_mid=short_mid, long_mid=long_mid,
        expected_credit=expected_credit,
        width=short_strike - long_strike,
        expiry=expiry, dte=actual_dte, spot=spot,
    )


# ---------- order submission ----------

def submit_open_order(cand: SpreadCandidate, qty: int) -> str | None:
    """Submit a multi-leg credit-spread limit order. Returns Alpaca order ID."""
    from alpaca.trading.enums import OrderClass, OrderSide, PositionIntent, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

    legs = [
        OptionLegRequest(
            symbol=cand.short_symbol, ratio_qty=1, side=OrderSide.SELL,
            position_intent=PositionIntent.SELL_TO_OPEN,
        ),
        OptionLegRequest(
            symbol=cand.long_symbol, ratio_qty=1, side=OrderSide.BUY,
            position_intent=PositionIntent.BUY_TO_OPEN,
        ),
    ]
    limit_credit = round(cand.expected_credit * config.SPREAD_LIMIT_FILL_FRAC, 2)
    req = LimitOrderRequest(
        order_class=OrderClass.MLEG,
        legs=legs, qty=qty,
        time_in_force=TimeInForce.DAY,
        limit_price=limit_credit,
    )
    client = _trading_client()
    order = client.submit_order(req)
    return str(order.id)


def submit_close_order(pos: SpreadPosition, limit_debit: float) -> str | None:
    from alpaca.trading.enums import OrderClass, OrderSide, PositionIntent, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

    legs = [
        OptionLegRequest(
            symbol=pos.short_symbol, ratio_qty=1, side=OrderSide.BUY,
            position_intent=PositionIntent.BUY_TO_CLOSE,
        ),
        OptionLegRequest(
            symbol=pos.long_symbol, ratio_qty=1, side=OrderSide.SELL,
            position_intent=PositionIntent.SELL_TO_CLOSE,
        ),
    ]
    req = LimitOrderRequest(
        order_class=OrderClass.MLEG,
        legs=legs, qty=pos.qty,
        time_in_force=TimeInForce.DAY,
        limit_price=round(limit_debit, 2),
    )
    client = _trading_client()
    order = client.submit_order(req)
    return str(order.id)


# ---------- entry scan ----------

def _format_strike(strike: float) -> str:
    """Render a strike price compactly: $1060 not $1060.0."""
    return f"${strike:g}"


def _format_open_alert(cand: SpreadCandidate, qty: int, order_id: str | None, dry_run: bool) -> tuple[str, str]:
    prefix = "[DRY] " if dry_run else ""
    max_gain = cand.expected_credit * 100 * qty
    max_loss = cand.max_loss_per_spread * 100 * qty
    title = (f"💰 {prefix}Opened {cand.ticker} "
             f"{_format_strike(cand.short_strike)}p/{_format_strike(cand.long_strike)}p "
             f"· +${max_gain:,.0f} max")
    body = (
        f"Spot ${cand.spot:.2f} · {cand.dte} DTE\n"
        f"Credit ${cand.expected_credit:.2f}/sh (max gain ${max_gain:,.0f})\n"
        f"Max loss: ${max_loss:,.0f} · expires {cand.expiry}"
        + (f"\nOrder: {order_id}" if order_id else "")
    )
    return title, body


def daily_entry_scan(notifiers: list[Notifier], dry_run: bool = False,
                     push_individual: bool = True) -> ScanSummary:
    """Look for new entries. Skips tickers with existing open positions and
    enforces global concurrency + risk limits.

    If `push_individual` is False, suppresses per-action notifications so the
    caller can build a consolidated summary push instead. Returns ScanSummary."""
    summary = ScanSummary(strategy="bull_put", opens=[], closes=[], notes=[], dry_run=dry_run)

    open_positions = reconcile_with_alpaca()
    open_tickers = {p.ticker for p in open_positions}
    open_count = len(open_positions)
    open_risk = sum(p.max_loss_total for p in open_positions)
    submitted = 0

    print(f"  [entry-scan] currently open: {open_count} positions on {sorted(open_tickers)}, "
          f"total max-loss ${open_risk:,.0f}")

    if open_count >= config.SPREAD_MAX_CONCURRENT:
        msg = f"at max concurrency ({config.SPREAD_MAX_CONCURRENT})"
        print(f"  [entry-scan] {msg}; skipping")
        summary.notes.append(msg)
        return summary

    for ticker in config.SPREAD_TICKERS:
        if ticker in open_tickers:
            continue
        if open_count + submitted >= config.SPREAD_MAX_CONCURRENT:
            break

        cand = find_bull_put_candidate(ticker)
        if not cand:
            print(f"  [{ticker}] no eligible spread")
            continue

        prospective_risk = cand.max_loss_per_spread * 100 * config.SPREAD_QTY_PER_TRADE
        if open_risk + prospective_risk > config.SPREAD_MAX_TOTAL_RISK:
            print(f"  [{ticker}] would exceed max total risk "
                  f"(${open_risk:,.0f} + ${prospective_risk:,.0f} > ${config.SPREAD_MAX_TOTAL_RISK:,.0f})")
            continue

        order_id: str | None = None
        if not dry_run and config.SPREAD_AUTO_SUBMIT:
            try:
                order_id = submit_open_order(cand, qty=config.SPREAD_QTY_PER_TRADE)
            except Exception as e:
                print(f"  [{ticker}] order submission failed: {e}")
                continue

            pos = SpreadPosition(
                ticker=ticker,
                short_symbol=cand.short_symbol, long_symbol=cand.long_symbol,
                short_strike=cand.short_strike, long_strike=cand.long_strike,
                width=cand.width, entry_credit=cand.expected_credit,
                expiry=cand.expiry.isoformat(),
                open_date=datetime.now(timezone.utc).isoformat(),
                qty=config.SPREAD_QTY_PER_TRADE,
                open_order_id=order_id,
            )
            _append_state(pos)

        # bookkeeping happens whether or not we actually submitted, so
        # dry-runs and alert-only modes still respect concurrency + risk caps
        open_risk += prospective_risk
        submitted += 1

        max_loss = cand.max_loss_per_spread * 100 * config.SPREAD_QTY_PER_TRADE
        max_gain = cand.expected_credit * 100 * config.SPREAD_QTY_PER_TRADE
        summary.opens.append({
            "ticker": ticker,
            "label": f"{ticker} {cand.short_strike:g}p/{cand.long_strike:g}p",
            "cost": max_loss,                 # capital at risk
            "credit": max_gain,
            "expiry": cand.expiry.isoformat(),
            "dte": cand.dte,
        })

        title, body = _format_open_alert(cand, config.SPREAD_QTY_PER_TRADE,
                                         order_id, dry_run or not config.SPREAD_AUTO_SUBMIT)
        if push_individual:
            dispatch(notifiers, title, body, priority=PRIORITY_HIGH, tags="moneybag")
        print(f"  [{ticker}] {title}")

    return summary


# ---------- exit monitor ----------

def _current_spread_liability(short_symbol: str, long_symbol: str) -> float | None:
    quotes = get_chain_snapshots([short_symbol, long_symbol])
    sq = quotes.get(short_symbol)
    lq = quotes.get(long_symbol)
    if not sq or not lq:
        return None
    short_bid, short_ask = float(sq.bid_price or 0), float(sq.ask_price or 0)
    long_bid, long_ask = float(lq.bid_price or 0), float(lq.ask_price or 0)
    short_mid = (short_bid + short_ask) / 2 if short_bid and short_ask else short_ask or short_bid
    long_mid = (long_bid + long_ask) / 2 if long_bid and long_ask else long_bid or long_ask
    return short_mid - long_mid


def monitor_exits(notifiers: list[Notifier], dry_run: bool = False) -> int:
    """For each open spread, check if profit target hit; if so close."""
    open_positions = reconcile_with_alpaca()
    if not open_positions:
        return 0
    closed = 0
    for pos in open_positions:
        liability = _current_spread_liability(pos.short_symbol, pos.long_symbol)
        if liability is None:
            continue
        # pnl per share = entry_credit - current_liability
        pnl_per_share = pos.entry_credit - liability
        target_pnl = pos.entry_credit * config.SPREAD_PROFIT_TARGET
        if pnl_per_share < target_pnl:
            continue

        # hit profit target → submit close
        order_id: str | None = None
        if not dry_run and config.SPREAD_AUTO_SUBMIT:
            try:
                # be willing to pay slightly above current liability for a fast fill
                limit_debit = liability * 1.05
                order_id = submit_close_order(pos, limit_debit)
            except Exception as e:
                print(f"  [{pos.ticker}] close-order submission failed: {e}")
                continue
            pos.status = "closed"
            pos.close_date = datetime.now(timezone.utc).isoformat()
            pos.close_debit = liability
            pos.realized_pnl = pnl_per_share * pos.qty * 100
            pos.close_order_id = order_id
            _append_state(pos)
            closed += 1

        prefix = "[DRY] " if dry_run else ""
        realized_dollars = pnl_per_share * pos.qty * 100
        pct_of_credit = pnl_per_share / pos.entry_credit * 100
        emoji = "✅" if realized_dollars >= 0 else "❌"
        sign = "+" if realized_dollars >= 0 else "-"
        title = (f"{emoji} {prefix}Closed {pos.ticker} "
                 f"{_format_strike(pos.short_strike)}p/{_format_strike(pos.long_strike)}p "
                 f"· {sign}${abs(realized_dollars):,.0f} ({pct_of_credit:+.0f}%)")
        body = (
            f"Entry credit: ${pos.entry_credit:.2f}/sh\n"
            f"Closed at:    ${liability:.2f}/sh\n"
            f"Realized P&L: {sign}${abs(realized_dollars):,.0f}\n"
            f"Expiry: {pos.expiry}"
        )
        tags = "white_check_mark" if realized_dollars >= 0 else "x"
        dispatch(notifiers, title, body, priority=PRIORITY_HIGH, tags=tags)
        print(f"  [{pos.ticker}] {title}")
    return closed
