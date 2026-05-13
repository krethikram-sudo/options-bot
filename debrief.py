"""End-of-day debrief — multi-strategy version.

Pulls each strategy's state, today's account snapshot, and history. Produces
a single push with per-strategy performance + cross-strategy totals + notes.

Each day's debrief is appended to `logs/debriefs.jsonl` so the next day's
debrief can compute trends and the user can review history.
"""
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import config
from alerts import PRIORITY_DEFAULT, dispatch
from chain_trader import (chain_open_positions, chain_realized_pnl_today,
                          chain_total_value)
from equity_trader import (rotation_open_positions, rotation_realized_pnl_today,
                           trend_open_positions, trend_realized_pnl_today)
from news import is_material, load_news_since
from report import _money, _pct, _signed_money, get_summary
from spread_trader import load_state as load_spread_state
from straddle_trader import (straddle_open_positions,
                             straddle_realized_pnl_today)

ET = ZoneInfo("America/New_York")
DEBRIEF_PATH = Path("logs/debriefs.jsonl")


def load_debrief_history() -> list[dict]:
    if not DEBRIEF_PATH.exists():
        return []
    out = []
    with DEBRIEF_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def save_debrief(data: dict) -> None:
    DEBRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEBRIEF_PATH.open("a") as f:
        f.write(json.dumps(data) + "\n")


# ---------- per-strategy state collectors ----------

def _spread_state_for_today(today: date) -> dict:
    state = load_spread_state()
    today_iso = today.isoformat()
    closed_today = [
        p for p in state.values()
        if p.status == "closed" and p.close_date and p.close_date.startswith(today_iso)
    ]
    opened_today = [
        p for p in state.values()
        if p.open_date and p.open_date.startswith(today_iso)
    ]
    open_pos = [p for p in state.values() if p.status == "open"]
    return {
        "opened": len(opened_today),
        "closed": len(closed_today),
        "open_count": len(open_pos),
        "open_risk": sum(p.max_loss_total for p in open_pos),
        "realized_today": sum(p.realized_pnl or 0 for p in closed_today),
        "closed_details": [{
            "ticker": p.ticker, "short": p.short_strike, "long": p.long_strike,
            "pnl": p.realized_pnl or 0,
            "pct_of_max": (p.realized_pnl / (p.entry_credit * p.qty * 100) * 100) if p.entry_credit else 0,
        } for p in closed_today],
        "near_expiry": [(p.ticker, (date.fromisoformat(p.expiry) - today).days)
                        for p in open_pos
                        if (date.fromisoformat(p.expiry) - today).days <= 7],
    }


def _trend_state_for_today(today: date) -> dict:
    open_pos = trend_open_positions()
    return {
        "open_count": len(open_pos),
        "open_capital": sum(p.entry_price * p.shares for p in open_pos),
        "realized_today": trend_realized_pnl_today(today),
        "tickers": sorted({p.ticker for p in open_pos}),
    }


def _rotation_state_for_today(today: date) -> dict:
    open_pos = rotation_open_positions()
    return {
        "open_count": len(open_pos),
        "open_capital": sum(p.entry_price * p.shares for p in open_pos),
        "realized_today": rotation_realized_pnl_today(today),
        "tickers": sorted({p.ticker for p in open_pos}),
    }


def _straddle_state_for_today(today: date) -> dict:
    open_pos = straddle_open_positions()
    return {
        "open_count": len(open_pos),
        "open_capital": sum(p.entry_cost_total for p in open_pos),
        "realized_today": straddle_realized_pnl_today(today),
        "tickers": sorted({p.ticker for p in open_pos}),
    }


def _chain_state_for_today(today: date) -> dict:
    pos = chain_open_positions()
    n = sum(1 for p in pos.values() if float(p.get("shares", 0)) > 0)
    invested = sum(float(p.get("total_invested", 0)) for p in pos.values())
    cur_value = chain_total_value(use_last_price=True)
    return {
        "open_count": n,
        "invested": invested,
        "current_value": cur_value,
        "unrealized": cur_value - invested,
        "realized_today": chain_realized_pnl_today(today),
    }


def _news_for_today(tickers: list[str]) -> dict:
    """Aggregate today's news for the universe (last 24h)."""
    arts = load_news_since(hours_back=24)
    universe = set(tickers)
    relevant = [a for a in arts if any(s in universe for s in (a.get("symbols") or []))]
    material = [a for a in relevant if is_material(a)]

    by_ticker: dict[str, int] = {}
    for a in material:
        for s in a.get("symbols") or []:
            if s in universe:
                by_ticker[s] = by_ticker.get(s, 0) + 1

    top = sorted(material, key=lambda a: a.get("created_at") or "", reverse=True)
    return {
        "total": len(relevant),
        "material": len(material),
        "by_ticker": by_ticker,
        "top_headlines": [a.get("headline", "") for a in top],
    }


# ---------- learnings ----------

def _build_learnings(spread: dict, trend: dict, rotation: dict, straddle: dict,
                     account: dict, history: list[dict]) -> list[str]:
    notes: list[str] = []

    # Spread risk utilization
    spread_risk_pct = (spread["open_risk"] / config.SPREAD_MAX_TOTAL_RISK * 100) if config.SPREAD_MAX_TOTAL_RISK else 0
    if spread_risk_pct > 90:
        notes.append(f"Spread risk cap nearly maxed ({spread_risk_pct:.0f}%) — no new spreads until existing close")
    elif spread_risk_pct < 30 and spread["open_count"] < config.SPREAD_MAX_CONCURRENT:
        notes.append(f"Spread risk underutilized ({spread_risk_pct:.0f}%) — could increase qty or lower delta")

    # Near-expiry spreads
    for ticker, dte in spread["near_expiry"]:
        notes.append(f"Spread {ticker} has {dte} DTE — close or roll soon")

    # Trend-following coverage
    expected_trend_count = len(config.TREND_TICKERS)
    if trend["open_count"] == 0:
        notes.append("Trend-following: 0 open positions — all 9 tickers below 50-SMA?")
    elif trend["open_count"] < expected_trend_count // 2:
        notes.append(f"Trend-following: only {trend['open_count']}/{expected_trend_count} above 50-SMA — possible regime softening")

    # Rotation status
    if rotation["open_count"] == 0:
        notes.append("Rotation: no positions yet — first rebalance pending")
    elif rotation["open_count"] != config.ROTATION_TOP_N:
        notes.append(f"Rotation: {rotation['open_count']} positions, expected {config.ROTATION_TOP_N} — investigate")

    # Straddle activity
    if straddle["realized_today"] != 0:
        sign = "+" if straddle["realized_today"] >= 0 else "-"
        notes.append(f"Straddle settled today: {sign}${abs(straddle['realized_today']):,.0f}")

    # Day P&L vs cumulative
    today_total = (spread["realized_today"] + trend["realized_today"]
                   + rotation["realized_today"] + straddle["realized_today"])
    if abs(today_total) > 1000:
        sign = "+" if today_total >= 0 else "-"
        notes.append(f"Strategy realized today: {sign}${abs(today_total):,.0f} (across all sleeves)")

    return notes


# ---------- main ----------

def generate_debrief() -> dict:
    today = datetime.now(ET).date()
    summary = get_summary()

    spread = _spread_state_for_today(today)
    trend = _trend_state_for_today(today)
    rotation = _rotation_state_for_today(today)
    straddle = _straddle_state_for_today(today)
    chain = _chain_state_for_today(today)
    news = _news_for_today(config.TICKERS)

    realized_today_total = (spread["realized_today"] + trend["realized_today"]
                            + rotation["realized_today"] + straddle["realized_today"]
                            + chain["realized_today"])

    history = load_debrief_history()
    cumulative = realized_today_total + sum(d.get("realized_total", 0) for d in history)

    learnings = _build_learnings(
        spread, trend, rotation, straddle,
        account={"equity": summary["equity"], "day_change": summary["day_change"]},
        history=history,
    )

    return {
        "date": today.isoformat(),
        "equity": summary["equity"],
        "day_change": summary["day_change"],
        "day_pct": summary["day_pct"],
        "starting_capital": summary["starting_capital"],
        "lifetime_change": summary["lifetime_change"],
        "lifetime_pct": summary["lifetime_pct"],
        "unrealized": summary["unrealized"],
        "realized_total": realized_today_total,
        "cumulative_realized": cumulative,
        "spread": spread,
        "trend": trend,
        "rotation": rotation,
        "straddle": straddle,
        "chain": chain,
        "news": news,
        "learnings": learnings,
    }


def format_debrief(d: dict) -> tuple[str, str]:
    life_pct = d.get("lifetime_pct", 0.0)
    title = (f"🔍 EOD · {_money(d['equity'])} · "
             f"day {_pct(d['day_pct'])} · life {_pct(life_pct)}")

    L: list[str] = []

    # Performance block
    L.append("📊 Performance")
    L.append(f"  Day:  {_signed_money(d['day_change'])} ({_pct(d['day_pct'])})")
    if "lifetime_change" in d:
        start = d.get("starting_capital", 100000.0)
        L.append(f"  Life: {_signed_money(d['lifetime_change'])} ({_pct(life_pct)}) "
                 f"vs {_money(start)} start")
    if d["realized_total"]:
        L.append(f"  Realized (4 sleeves): {_signed_money(d['realized_total'])}")
    if d["unrealized"]:
        L.append(f"  Unrealized (open): {_signed_money(d['unrealized'])}")

    # Per-strategy block
    L.append("")
    L.append("🎛️ Sleeves")
    s = d["spread"]
    L.append(f"  Spreads: {s['open_count']} open · risk {_money(s['open_risk'])} · "
             f"realized {_signed_money(s['realized_today'])}")
    if s["closed_details"]:
        for c in s["closed_details"]:
            L.append(f"    closed {c['ticker']} {c['short']:g}p/{c['long']:g}p: "
                     f"{_signed_money(c['pnl'])} ({c['pct_of_max']:+.0f}% of max)")

    t = d["trend"]
    L.append(f"  Trend: {t['open_count']} positions · capital {_money(t['open_capital'])} · "
             f"realized {_signed_money(t['realized_today'])}")
    if t["tickers"]:
        L.append(f"    holding: {', '.join(t['tickers'])}")

    r = d["rotation"]
    L.append(f"  Rotation: {r['open_count']} positions · capital {_money(r['open_capital'])} · "
             f"realized {_signed_money(r['realized_today'])}")
    if r["tickers"]:
        L.append(f"    holding: {', '.join(r['tickers'])}")

    st = d["straddle"]
    L.append(f"  Straddles: {st['open_count']} open · cost basis {_money(st['open_capital'])} · "
             f"realized {_signed_money(st['realized_today'])}")
    if st["tickers"]:
        L.append(f"    holding: {', '.join(st['tickers'])}")

    ch = d["chain"]
    L.append(f"  AI Chain: {ch['open_count']} positions · invested {_money(ch['invested'])} "
             f"· now {_money(ch['current_value'])} · unrealized {_signed_money(ch['unrealized'])}")

    # News
    n = d.get("news") or {}
    if n.get("material", 0) > 0:
        L.append("")
        L.append("📰 News (24h)")
        L.append(f"  Material articles: {n['material']} of {n['total']} relevant to universe")
        if n.get("by_ticker"):
            sorted_t = sorted(n["by_ticker"].items(), key=lambda x: -x[1])
            line = " · ".join(f"{t}:{c}" for t, c in sorted_t)
            L.append(f"  By ticker: {line}")
        for h in n.get("top_headlines") or []:
            L.append(f"  • {h}")

    # Cumulative
    L.append("")
    L.append("📒 Cumulative")
    L.append(f"  Realized since start: {_signed_money(d['cumulative_realized'])}")

    # Notes
    if d["learnings"]:
        L.append("")
        L.append("💡 Notes")
        for note in d["learnings"]:
            L.append(f"  • {note}")

    return title, "\n".join(L)


def send_eod_debrief(notifiers) -> None:
    data = generate_debrief()
    save_debrief(data)
    title, body = format_debrief(data)
    dispatch(notifiers, title, body, priority=PRIORITY_DEFAULT, tags="brain")
    print(f"  [debrief] {title}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    data = generate_debrief()
    title, body = format_debrief(data)
    print(title)
    print(body)
