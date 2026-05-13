"""News fetcher built on Alpaca's free News API.

Two halves:
  - fetch_news / fetch_and_log: pull recent news, dedupe, append to JSONL log
  - is_material / material_articles_for: keyword filter so we can surface
    "this matters" items in the morning push and EOD debrief

Intelligent analysis (relevance, sentiment, strategy implications) happens
during the live 6 PM Claude Code session, not here. The bot just maintains
the raw record.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

NEWS_LOG = Path("logs/news.jsonl")

# Keywords that flag an article as worth attention. Lower-case match against
# headline + summary. Conservative — false positives are OK; we just surface
# the count and let the user / EOD analysis judge.
MATERIAL_KEYWORDS = [
    # earnings / guidance
    "earnings", "eps", "revenue", "guidance", "beat", "miss", "results",
    "outlook", "forecast", "raises", "lowered",
    # M&A / corporate actions
    "acquisition", "merger", "buyout", "stake", "spin-off", "split",
    # regulatory / legal
    "lawsuit", "investigation", "antitrust", "ftc", "sec", "doj",
    "subpoena", "fine", "settlement",
    # analyst actions
    "upgrade", "downgrade", "price target", "rating", "initiates",
    "outperform", "underperform", "neutral",
    # product / strategic
    "launch", "partnership", "contract", "deal", "supplier",
    # crisis
    "halt", "warning", "recall", "delay", "drop", "plunge", "tumbles",
    "crash", "soar", "rally", "surge",
    # sector-specific (AI infra)
    "ai chip", "data center", "hyperscale", "tsmc", "fab",
]


def _news_client():
    from alpaca.data.historical.news import NewsClient
    return NewsClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_API_SECRET"],
    )


def fetch_news(symbols: list[str], hours_back: int = 24, limit: int = 50) -> list[dict]:
    """Pull recent news from Alpaca for the given symbols. Returns flat list of dicts."""
    from alpaca.data.requests import NewsRequest

    client = _news_client()
    req = NewsRequest(
        symbols=",".join(symbols),
        start=datetime.now(timezone.utc) - timedelta(hours=hours_back),
        limit=limit,
    )
    response = client.get_news(req)

    articles: list[dict] = []
    # NewsSet wraps data as a dict {"news": [<News model object>...]}
    raw_news = []
    if hasattr(response, "data") and isinstance(response.data, dict):
        raw_news = response.data.get("news", [])
    for item in raw_news:
        ts = getattr(item, "created_at", None)
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else (ts if isinstance(ts, str) else None)
        symbols = getattr(item, "symbols", None) or []
        articles.append({
            "id": str(getattr(item, "id", "")),
            "headline": getattr(item, "headline", "") or "",
            "summary": (getattr(item, "summary", "") or "")[:600],
            "author": getattr(item, "author", None),
            "created_at": ts_iso,
            "url": getattr(item, "url", None),
            "symbols": list(symbols),
        })
    return articles


def is_material(article: dict) -> bool:
    text = f"{article.get('headline', '')} {article.get('summary', '')}".lower()
    return any(kw in text for kw in MATERIAL_KEYWORDS)


def material_articles_for(ticker: str, hours_back: int = 24) -> list[dict]:
    """Pull news for a specific ticker and filter to material items."""
    arts = fetch_news([ticker], hours_back=hours_back)
    relevant = [a for a in arts if ticker in a.get("symbols", [])]
    return [a for a in relevant if is_material(a)]


def log_news_batch(articles: list[dict]) -> int:
    """Append articles to the news log, deduping by id. Returns # new appended."""
    NEWS_LOG.parent.mkdir(parents=True, exist_ok=True)
    seen_ids: set[str] = set()
    if NEWS_LOG.exists():
        with NEWS_LOG.open() as f:
            for line in f:
                try:
                    a = json.loads(line)
                    seen_ids.add(a.get("id"))
                except Exception:
                    pass
    new_count = 0
    with NEWS_LOG.open("a") as f:
        for a in articles:
            if a.get("id") in seen_ids:
                continue
            seen_ids.add(a.get("id"))
            f.write(json.dumps(a) + "\n")
            new_count += 1
    return new_count


def fetch_and_log(tickers: list[str], hours_back: int = 24) -> tuple[list[dict], int]:
    """Fetch news, dedupe-append to log, return (all_articles, new_count)."""
    arts = fetch_news(tickers, hours_back=hours_back)
    new_count = log_news_batch(arts)
    return arts, new_count


def load_news_since(hours_back: int = 24) -> list[dict]:
    """Load articles from the log with created_at within the last N hours."""
    if not NEWS_LOG.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    out: list[dict] = []
    with NEWS_LOG.open() as f:
        for line in f:
            try:
                a = json.loads(line)
                ts_str = a.get("created_at")
                if not ts_str:
                    continue
                ts = datetime.fromisoformat(ts_str)
                if ts >= cutoff:
                    out.append(a)
            except Exception:
                continue
    return out


def material_counts_by_ticker(hours_back: int = 24) -> dict[str, int]:
    """Aggregate material article counts per ticker from the log."""
    arts = load_news_since(hours_back=hours_back)
    counts: dict[str, int] = {}
    for a in arts:
        if not is_material(a):
            continue
        for s in a.get("symbols", []):
            counts[s] = counts.get(s, 0) + 1
    return counts
