"""Alert dispatch + dedup.

`Alert` is a per-bar signal; `Notifier` dispatches it. Notifiers also support
`notify_message(title, body, priority=, tags=)` for non-alert content like
daily reports, with priority and emoji tags pushed through to ntfy.

`AlertTracker` dedupes on (ticker, side, bar_time) so a single signal bar
only fires once across many polling cycles.
"""
import json
import os
import subprocess
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd


# ntfy priority strings
PRIORITY_MAX = "max"        # full screen / urgent
PRIORITY_HIGH = "high"      # high priority - buzzes loudly
PRIORITY_DEFAULT = "default"
PRIORITY_LOW = "low"        # silent
PRIORITY_MIN = "min"        # nearly hidden


@dataclass
class Alert:
    ticker: str
    side: str
    bar_time: pd.Timestamp
    spot: float
    rsi: float
    macd_hist: float

    def summary(self) -> str:
        return (
            f"{self.ticker:<6} {self.side.upper():<4} bar={self.bar_time:%Y-%m-%d %H:%M} "
            f"spot=${self.spot:.2f} RSI={self.rsi:.1f} hist={self.macd_hist:+.3f}"
        )

    def to_record(self) -> dict:
        d = asdict(self)
        d["bar_time"] = self.bar_time.isoformat()
        d["fired_at"] = datetime.now().isoformat(timespec="seconds")
        return d


class Notifier(ABC):
    @abstractmethod
    def notify(self, alert: Alert) -> None: ...

    def notify_message(self, title: str, body: str, **kwargs) -> None:
        """Override in subclasses that handle messages specially. Default: print."""
        print(f"\n=== {title} ===\n{body}\n")


class ConsoleNotifier(Notifier):
    def notify(self, alert: Alert) -> None:
        print(f"[{datetime.now():%H:%M:%S}] SIGNAL: {alert.summary()}")

    def notify_message(self, title: str, body: str, **kwargs) -> None:
        print(f"\n[{datetime.now():%H:%M:%S}] {title}\n{body}\n")


class DesktopNotifier(Notifier):
    """macOS desktop notification. May not appear from a launchd background
    process without entitlements; we keep it for foreground runs."""

    def _say(self, title: str, subtitle: str, body: str) -> None:
        title_e = title.replace('"', '\\"')
        sub_e = subtitle.replace('"', '\\"')
        body_e = body.replace('"', '\\"').replace("\n", " · ")
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{body_e}" with title "{title_e}" subtitle "{sub_e}"'],
                check=False, timeout=3,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def notify(self, alert: Alert) -> None:
        body = f"spot ${alert.spot:.2f}  RSI {alert.rsi:.1f}  hist {alert.macd_hist:+.3f}"
        self._say("Options Alert", f"{alert.ticker} {alert.side.upper()}", body)

    def notify_message(self, title: str, body: str, **kwargs) -> None:
        self._say("Options Bot", title, body)


class MobilePushNotifier(Notifier):
    """ntfy.sh push. Free, no signup. Topic is your password — anyone with
    the topic name can read your alerts.

    Auto-chunks long bodies. ntfy.sh free tier converts bodies > 4096 bytes
    to file attachments, which iOS displays as a download icon (not inline
    text). We split into multiple pushes labeled (1/N), (2/N), etc. preserving
    line boundaries so each fits inline.
    """

    SAFE_PUSH_LIMIT = 3800  # leave headroom under ntfy's 4096 cap

    def __init__(self, topic: str):
        self.topic = topic
        self.url = f"https://ntfy.sh/{topic}"

    @classmethod
    def from_env(cls) -> "MobilePushNotifier | None":
        topic = os.environ.get("NTFY_TOPIC")
        if not topic:
            print("WARNING: NTFY_TOPIC not set in .env, mobile push disabled")
            return None
        return cls(topic)

    def _post(self, title: str, body: str, *, tags: str = "", priority: str = PRIORITY_DEFAULT,
              max_retries: int = 3) -> bool:
        """POST to ntfy with retry on transient timeouts. Returns True on success."""
        headers = {
            "Title": title.encode("utf-8").decode("latin-1", "replace"),
            "Priority": priority,
        }
        if tags:
            headers["Tags"] = tags
        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(self.url, data=body.encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if 200 <= resp.status < 300:
                        if attempt > 0:
                            print(f"  push ok on retry {attempt}: '{title[:50]}'")
                        return True
                    print(f"  push got HTTP {resp.status} for '{title[:50]}'")
                    return False
            except Exception as e:
                last_err = e
                # backoff: 0s, 1s, 3s between attempts
                if attempt < max_retries - 1:
                    import time as _time
                    _time.sleep(attempt * 2 + 1)
        print(f"  push failed after {max_retries} retries: {last_err} ('{title[:50]}')")
        return False

    def _split_body(self, body: str) -> list[str]:
        """Split body into <SAFE_PUSH_LIMIT chunks at line boundaries."""
        if len(body.encode("utf-8")) <= self.SAFE_PUSH_LIMIT:
            return [body]
        chunks: list[str] = []
        cur: list[str] = []
        cur_bytes = 0
        for line in body.split("\n"):
            line_bytes = len(line.encode("utf-8")) + 1  # +1 for the \n
            if cur and cur_bytes + line_bytes > self.SAFE_PUSH_LIMIT:
                chunks.append("\n".join(cur))
                cur = []
                cur_bytes = 0
            cur.append(line)
            cur_bytes += line_bytes
        if cur:
            chunks.append("\n".join(cur))
        return chunks

    def _post_chunked(self, title: str, body: str, *, tags: str, priority: str) -> None:
        chunks = self._split_body(body)
        if len(chunks) == 1:
            self._post(title, chunks[0], tags=tags, priority=priority)
            return
        n = len(chunks)
        for i, chunk in enumerate(chunks, 1):
            chunked_title = f"{title} ({i}/{n})"
            self._post(chunked_title, chunk, tags=tags, priority=priority)

    def notify(self, alert: Alert) -> None:
        # RSI/MACD signal alerts — informational, low priority (no sound)
        title = f"🔔 {alert.ticker} {alert.side} · ${alert.spot:.2f}"
        body = f"RSI {alert.rsi:.1f} · MACD hist {alert.macd_hist:+.3f}"
        self._post(title, body, priority=PRIORITY_LOW)

    def notify_message(
        self, title: str, body: str, *,
        priority: str = PRIORITY_DEFAULT, tags: str = "",
    ) -> None:
        self._post_chunked(title, body, tags=tags, priority=priority)


class FileLogger(Notifier):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def notify(self, alert: Alert) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(alert.to_record()) + "\n")

    def notify_message(self, title: str, body: str, **kwargs) -> None:
        report_path = self.path.with_name("reports.jsonl")
        with report_path.open("a") as f:
            f.write(json.dumps({
                "ts": datetime.now().isoformat(timespec="seconds"),
                "title": title,
                "body": body,
            }) + "\n")


def dispatch(notifiers: list[Notifier], title: str, body: str, *,
             priority: str = PRIORITY_DEFAULT, tags: str = "") -> None:
    """Send a message to all notifiers, passing priority + tags to those that support them."""
    for n in notifiers:
        try:
            n.notify_message(title, body, priority=priority, tags=tags)
        except Exception as e:
            print(f"  notify failed on {type(n).__name__}: {e}")


@dataclass
class ScanSummary:
    """Result of a daily strategy scan. Used to consolidate cross-strategy
    notifications instead of per-action pushes."""
    strategy: str               # 'bull_put' | 'trend_following' | 'rotational_momentum' | 'earnings_straddle'
    opens: list[dict]           # [{ticker, label, cost_or_credit, ...}]
    closes: list[dict]          # [{ticker, label, pnl, pct, reason, ...}]
    notes: list[str]            # any caveats (e.g. "skipped — risk cap maxed")
    dry_run: bool = False

    @property
    def total_actions(self) -> int:
        return len(self.opens) + len(self.closes)

    @property
    def total_capital_deployed(self) -> float:
        return sum(o.get("cost", 0) for o in self.opens)

    @property
    def total_realized_pnl(self) -> float:
        return sum(c.get("pnl", 0) for c in self.closes)


def send_consolidated_morning_summary(
    notifiers: list[Notifier],
    summaries: list[ScanSummary],
    news_counts: dict[str, int] | None = None,
    top_headlines: list[str] | None = None,
) -> None:
    """Build and send ONE morning push covering all strategy scans.
    Optionally append a news block summarizing last 24h material articles."""
    total_orders = sum(s.total_actions for s in summaries)
    if total_orders == 0:
        # nothing happened — send a minimal "all quiet" push
        dispatch(notifiers,
                 "🌅 Morning scan · no new entries",
                 "No strategies fired. All positions held.",
                 priority=PRIORITY_DEFAULT, tags="zzz")
        return

    title = f"🚀 Morning scan · {total_orders} orders"

    L: list[str] = []
    total_deployed = 0.0
    total_realized = 0.0

    for s in summaries:
        emoji_by_strategy = {
            "bull_put": "💰", "trend_following": "📈",
            "rotational_momentum": "🔄", "earnings_straddle": "💎",
        }
        emoji = emoji_by_strategy.get(s.strategy, "•")
        nice_name = s.strategy.replace("_", " ").title()
        if s.total_actions == 0:
            L.append(f"{emoji} {nice_name}: no action")
            continue

        deployed = s.total_capital_deployed
        realized = s.total_realized_pnl
        total_deployed += deployed
        total_realized += realized

        parts: list[str] = []
        if s.opens:
            parts.append(f"{len(s.opens)} opened")
        if s.closes:
            parts.append(f"{len(s.closes)} closed")
        if deployed > 0:
            parts.append(f"${deployed:,.0f} deployed")
        if realized != 0:
            sign = "+" if realized >= 0 else "-"
            parts.append(f"P&L {sign}${abs(realized):,.0f}")

        L.append(f"{emoji} {nice_name}: {' · '.join(parts)}")
        # show ticker labels in full (no truncation)
        if s.opens:
            tickers = " · ".join(o.get("label", o.get("ticker", "?")) for o in s.opens)
            L.append(f"   open: {tickers}")
        if s.closes:
            close_lines = []
            for c in s.closes:
                pnl = c.get("pnl", 0)
                sign = "+" if pnl >= 0 else "-"
                close_lines.append(f"{c.get('ticker', '?')} {sign}${abs(pnl):,.0f}")
            L.append(f"   close: {' · '.join(close_lines)}")
        for note in s.notes:
            L.append(f"   ! {note}")

    L.append("")
    L.append(f"Capital deployed: ${total_deployed:,.0f}")
    if total_realized != 0:
        sign = "+" if total_realized >= 0 else "-"
        L.append(f"Realized P&L:    {sign}${abs(total_realized):,.0f}")

    # News block — show material counts per ticker + top headlines
    if news_counts:
        # filter to tickers with positions opened today + any with high counts
        open_tickers = {o.get("ticker") for s in summaries for o in s.opens}
        relevant_counts = {t: c for t, c in news_counts.items()
                           if t in open_tickers or c >= 3}
        if relevant_counts:
            L.append("")
            L.append("📰 News (24h, material)")
            sorted_counts = sorted(relevant_counts.items(), key=lambda x: -x[1])
            line = " · ".join(f"{t}:{c}" for t, c in sorted_counts)
            L.append(f"   {line}")
    if top_headlines:
        for h in top_headlines:
            L.append(f"   • {h}")

    dispatch(notifiers, title, "\n".join(L), priority=PRIORITY_HIGH, tags="rocket")


class AlertTracker:
    def __init__(self) -> None:
        self._seen: set[tuple[str, str, pd.Timestamp]] = set()

    def is_new(self, alert: Alert) -> bool:
        key = (alert.ticker, alert.side, alert.bar_time)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True
