"""Live signal monitor + daily reports.

Polls every `POLL_INTERVAL_SECONDS` during US market hours (9:30-16:00 ET, Mon-Fri).
Pulls real-time IEX bars from Alpaca, computes RSI/MACD/signals, and dispatches
to the configured notifiers when a fresh signal appears.

Sends two reports per trading day:
  - Open: equity / cash / open positions, on first scan after 9:30 ET
  - Close: equity, day P&L, all of today's fills, after 16:00 ET

Requires ALPACA_API_KEY / ALPACA_API_SECRET / NTFY_TOPIC in `.env`.
"""
import time as _time
from datetime import datetime, time as _dt_time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

import config
from alerts import (Alert, AlertTracker, ConsoleNotifier, DesktopNotifier,
                    FileLogger, MobilePushNotifier)
from alerts import (PRIORITY_DEFAULT, dispatch,
                    send_consolidated_morning_summary)
from data_fetcher import fetch_alpaca_bars
from debrief import send_eod_debrief
from equity_trader import daily_rotation_scan, daily_trend_scan
from news import (fetch_and_log, is_material, load_news_since,
                  material_counts_by_ticker)
from report import send_report
from signals import compute_signals
from spread_trader import daily_entry_scan, monitor_exits, open_positions_from_state
from strategy import Strategy

# Premium strategies — paid subscribers receive these via a private companion
# repo (see premium/README.md). Public bot runs cleanly without them.
try:
    from premium.chain_trader import daily_chain_scan
    HAS_CHAIN = True
except ImportError:
    HAS_CHAIN = False
    def daily_chain_scan(notifiers, push_individual=True):
        return {"label": "ai full chain (premium — not installed)", "opened": [], "closed": [], "skipped": True}

try:
    from premium.straddle_trader import daily_straddle_scan
    HAS_STRADDLE = True
except ImportError:
    HAS_STRADDLE = False
    def daily_straddle_scan(notifiers, push_individual=True):
        return {"label": "earnings straddles (premium — not installed)", "opened": [], "closed": [], "skipped": True}

load_dotenv()

ET = ZoneInfo("America/New_York")
PT = ZoneInfo("America/Los_Angeles")
ALERT_LOG_PATH = "logs/alerts.jsonl"
CLOSE_REPORT_DELAY_MIN = 5  # send close report at 16:05 ET so fills/marks settle
DEBRIEF_REMINDER_HOUR_PT = 18  # 6 PM Pacific — daily prompt to start a Claude Code session


def market_is_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(ET)
    if now.weekday() >= 5:
        return False
    return _dt_time(9, 30) <= now.time() <= _dt_time(16, 0)


def scan_once(tracker: AlertTracker, notifiers: list, s: Strategy) -> int:
    fired = 0
    for ticker in config.TICKERS:
        try:
            bars = fetch_alpaca_bars(ticker, interval_minutes=5, lookback_minutes=7200)
            if bars.empty or len(bars) < 50:
                continue
            sig = compute_signals(bars, s)
            last = sig.iloc[-1]
            is_call = bool(last["call_signal"])
            is_put = bool(last["put_signal"])
            if not (is_call or is_put):
                continue
            alert = Alert(
                ticker=ticker,
                side="call" if is_call else "put",
                bar_time=sig.index[-1],
                spot=float(last["close"]),
                rsi=float(last["rsi"]),
                macd_hist=float(last["hist"]),
            )
            if tracker.is_new(alert):
                for n in notifiers:
                    n.notify(alert)
                fired += 1
        except Exception as e:
            print(f"  [{ticker}] error: {e}")
    return fired


def _build_notifiers() -> list:
    notifiers = [ConsoleNotifier(), DesktopNotifier(), FileLogger(ALERT_LOG_PATH)]
    push = MobilePushNotifier.from_env()
    if push:
        notifiers.append(push)
    return notifiers


def run() -> None:
    s = Strategy()
    tracker = AlertTracker()
    notifiers = _build_notifiers()

    print(f"Live signal monitor + daily reports")
    print(f"  Tickers     : {', '.join(config.TICKERS)}")
    print(f"  Strategy    : {s.label()}")
    print(f"  Poll every  : {config.POLL_INTERVAL_SECONDS}s")
    print(f"  Logging to  : {ALERT_LOG_PATH}")
    print(f"  Notifiers   : {', '.join(type(n).__name__ for n in notifiers)}")
    print(f"  Reminder    : signals != edge. Tuner showed 46% directional accuracy.")
    print()

    last_open_date = None
    last_close_date = None
    last_debrief_date = None
    last_entry_scan_date = None
    last_reminder_date = None
    intraday_sent_today: set[tuple[int, int]] = set()  # (hour, minute_slot) tuples (10:00, 10:30, ..., 15:30)
    intraday_sent_date = None

    while True:
        now = datetime.now(ET)
        today = now.date()

        if market_is_open(now):
            if last_open_date != today:
                print(f"[{now:%H:%M:%S ET}] sending open report...")
                send_report(notifiers, "open")
                last_open_date = today

            # intraday check-in every 30 min (10:00, 10:30, ..., 15:30 ET). Reset on day change.
            if intraday_sent_date != today:
                intraday_sent_today = set()
                intraday_sent_date = today
            slot: tuple[int, int] | None = None
            if 10 <= now.hour <= 15:
                slot_minute = 0 if now.minute < 30 else 30
                slot = (now.hour, slot_minute)
            if slot is not None and slot not in intraday_sent_today:
                label = f"{slot[0]:02d}:{slot[1]:02d}"
                print(f"[{now:%H:%M:%S ET}] refreshing news + sending {label} report...")
                # quick news refresh — focus on tickers with open positions
                try:
                    open_underlyings = sorted({p.ticker for p in open_positions_from_state()})
                    if open_underlyings:
                        fetch_and_log(open_underlyings, hours_back=2)
                except Exception as e:
                    print(f"  intraday news fetch failed: {e}")
                try:
                    send_report(notifiers, "intraday")
                except Exception as e:
                    print(f"  intraday report failed: {e}")
                intraday_sent_today.add(slot)

            # daily entry scan: once per market day - all four strategies, ONE consolidated push
            if last_entry_scan_date != today:
                print(f"[{now:%H:%M:%S ET}] fetching last 24h news for all tickers...")
                news_counts: dict[str, int] = {}
                top_headlines: list[str] = []
                try:
                    arts, n_new = fetch_and_log(config.TICKERS, hours_back=24)
                    print(f"  news: {len(arts)} fetched, {n_new} new")
                    news_counts = material_counts_by_ticker(hours_back=24)
                    top_headlines = [a["headline"] for a in arts if is_material(a)][:3]
                except Exception as e:
                    print(f"  news fetch failed: {e}")

                print(f"[{now:%H:%M:%S ET}] running daily strategy scans (consolidated push)...")
                summaries = []
                for label, fn in (
                    ("bull put spreads",    lambda: daily_entry_scan(notifiers, push_individual=False)),
                    ("trend following",     lambda: daily_trend_scan(notifiers, push_individual=False)),
                    ("rotational momentum", lambda: daily_rotation_scan(notifiers, push_individual=False)),
                    ("earnings straddles",  lambda: daily_straddle_scan(notifiers, push_individual=False)),
                    ("ai full chain",       lambda: daily_chain_scan(notifiers, push_individual=False)),
                ):
                    try:
                        print(f"  --- {label} ---")
                        summaries.append(fn())
                    except Exception as e:
                        print(f"  {label} scan error: {e}")
                try:
                    send_consolidated_morning_summary(
                        notifiers, summaries,
                        news_counts=news_counts, top_headlines=top_headlines,
                    )
                except Exception as e:
                    print(f"  morning summary push error: {e}")
                last_entry_scan_date = today

            # exit monitor: every poll, but only if there are open positions
            if open_positions_from_state():
                try:
                    monitor_exits(notifiers)
                except Exception as e:
                    print(f"  exit monitor error: {e}")

            n = scan_once(tracker, notifiers, s)
            print(f"[{now:%H:%M:%S ET}] scanned {len(config.TICKERS)} tickers ({n} new)")
            _time.sleep(config.POLL_INTERVAL_SECONDS)
        else:
            close_cutoff = _dt_time(16, CLOSE_REPORT_DELAY_MIN)
            if (now.weekday() < 5
                    and now.time() >= close_cutoff
                    and last_close_date != today):
                print(f"[{now:%H:%M:%S ET}] sending close report...")
                send_report(notifiers, "close")
                last_close_date = today

            # EOD debrief: fire ~5 min after close report (16:10 ET)
            debrief_cutoff = _dt_time(16, CLOSE_REPORT_DELAY_MIN + 5)
            if (now.weekday() < 5
                    and now.time() >= debrief_cutoff
                    and last_debrief_date != today):
                print(f"[{now:%H:%M:%S ET}] sending EOD debrief...")
                try:
                    send_eod_debrief(notifiers)
                except Exception as e:
                    print(f"  debrief failed: {e}")
                last_debrief_date = today

            # Daily Claude Code session reminder: 6 PM Pacific weekdays
            now_pt = datetime.now(PT)
            if (now_pt.weekday() < 5
                    and now_pt.time() >= _dt_time(DEBRIEF_REMINDER_HOUR_PT, 0)
                    and last_reminder_date != now_pt.date()):
                print(f"[{now_pt:%H:%M:%S PT}] sending daily Claude Code session reminder...")
                try:
                    dispatch(
                        notifiers,
                        "🧠 Time to debrief in Claude Code",
                        ("Run `claude` in ~/options-bot/ to start the daily debrief session.\n"
                         "Review today's debrief, discuss what worked / didn't, and decide on any "
                         "strategy adjustments.\n\n"
                         "Today's debrief log: ~/options-bot/logs/debriefs.jsonl"),
                        priority=PRIORITY_DEFAULT,
                        tags="brain",
                    )
                except Exception as e:
                    print(f"  reminder failed: {e}")
                last_reminder_date = now_pt.date()

            print(f"[{now:%Y-%m-%d %H:%M:%S ET}] market closed; sleeping 5min")
            _time.sleep(300)


if __name__ == "__main__":
    run()
