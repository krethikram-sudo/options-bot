"""Generate (and optionally publish) a public daily summary of the bot's P&L.

Why this exists: the most credible thing a quant project can produce is an
audited live record. Backtests are easy to fake; daily public posts are not.
After ~90 days of this running, the record becomes the primary credibility
artifact for the project (and the gating evidence for offering a paid tier).

Two responsibilities, kept separate:
  - `format_public_post(d)` — turn a debrief dict into a ≤300-char post
  - `publish(text, image_path=None)` — post to Bluesky if credentials are set,
    otherwise just write to `logs/public_posts/YYYY-MM-DD.txt`

Bluesky is used (not Twitter) because the API is free. Set env vars:
  BLUESKY_HANDLE      e.g. "quietedge.bsky.social"
  BLUESKY_APP_PASSWORD  an app-password from https://bsky.app/settings/app-passwords
  BLUESKY_DRY_RUN=1   to skip actual posting (file write only)

If `atproto` is not installed or creds are missing, posting silently degrades
to file-write only. This makes the module a no-op for OSS users who haven't
set anything up.
"""
import json
import os
from datetime import date as date_cls
from pathlib import Path

PUBLIC_POST_DIR = Path("logs/public_posts")
BLUESKY_CHAR_LIMIT = 300


# ---------- post generation ----------

def _sleeve_line(label: str, emoji: str, body: str) -> str:
    return f"{emoji} {label}: {body}"


def _money(x: float) -> str:
    if abs(x) >= 1000:
        return f"${x/1000:,.1f}k"
    return f"${x:,.0f}"


def _signed_money(x: float) -> str:
    if x >= 0:
        return f"+{_money(x)}"
    return f"-{_money(abs(x))}"


def _pct(x: float) -> str:
    return f"{x:+.2f}%"


def format_public_post(d: dict) -> str:
    """Compose a ≤300-char post from a debrief dict (see debrief.generate_debrief)."""
    date_str = d["date"]
    day_pct = d.get("day_pct", 0.0)
    life_pct = d.get("lifetime_pct", 0.0)
    equity = d.get("equity", 0.0)

    spread = d.get("spread", {}) or {}
    trend = d.get("trend", {}) or {}
    rotation = d.get("rotation", {}) or {}
    straddle = d.get("straddle", {}) or {}
    chain = d.get("chain", {}) or {}

    # Header line — equity + day + life
    header = (
        f"Quiet Edge • {date_str}\n"
        f"Equity {_money(equity)} • day {_pct(day_pct)} • life {_pct(life_pct)}\n"
    )

    # Per-sleeve compact lines
    lines = [
        f"Spreads: {spread.get('open_count', 0)} open · "
        f"realized {_signed_money(spread.get('realized_today', 0))}",
        f"Trend: {trend.get('open_count', 0)} positions",
        f"Rotation: {rotation.get('open_count', 0)} positions",
        f"Straddles: {straddle.get('open_count', 0)} open",
        f"AI Chain: {chain.get('open_count', 0)} names",
    ]

    post = header + "\n".join(lines)

    # Hard char-limit safety — truncate the last sleeve line if we overflow
    if len(post) > BLUESKY_CHAR_LIMIT:
        post = post[:BLUESKY_CHAR_LIMIT - 1] + "…"

    return post


# ---------- publishing ----------

def _write_to_file(text: str, date_str: str) -> Path:
    PUBLIC_POST_DIR.mkdir(parents=True, exist_ok=True)
    out = PUBLIC_POST_DIR / f"{date_str}.txt"
    out.write_text(text + "\n")
    return out


def _post_to_bluesky(text: str) -> tuple[bool, str]:
    """Returns (ok, message). Silent no-op if creds/lib unavailable."""
    handle = os.environ.get("BLUESKY_HANDLE")
    pw = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not pw:
        return False, "no creds set (BLUESKY_HANDLE / BLUESKY_APP_PASSWORD)"

    if os.environ.get("BLUESKY_DRY_RUN") == "1":
        return True, "dry-run (BLUESKY_DRY_RUN=1)"

    try:
        from atproto import Client  # type: ignore
    except ImportError:
        return False, "atproto not installed — `pip install atproto`"

    try:
        client = Client()
        client.login(handle, pw)
        client.send_post(text=text)
        return True, f"posted to @{handle}"
    except Exception as e:
        return False, f"post failed: {e}"


def publish(text: str, date_str: str | None = None) -> dict:
    """Always saves to file; tries Bluesky if configured. Returns status dict."""
    date_str = date_str or date_cls.today().isoformat()
    file_path = _write_to_file(text, date_str)
    bsky_ok, bsky_msg = _post_to_bluesky(text)
    return {
        "file": str(file_path),
        "bluesky_ok": bsky_ok,
        "bluesky_msg": bsky_msg,
        "char_count": len(text),
    }


# ---------- entry point ----------

def publish_from_debrief(debrief_data: dict) -> dict:
    text = format_public_post(debrief_data)
    return publish(text, date_str=debrief_data.get("date"))


if __name__ == "__main__":
    # Manual run: read the most recent debrief and publish it.
    from dotenv import load_dotenv
    load_dotenv()

    debriefs_path = Path("logs/debriefs.jsonl")
    if not debriefs_path.exists():
        raise SystemExit("logs/debriefs.jsonl not found — run debrief.py first")

    last = None
    with debriefs_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    pass
    if not last:
        raise SystemExit("no parseable debrief found")

    text = format_public_post(last)
    print("=" * 60)
    print(f"POST PREVIEW ({len(text)}/{BLUESKY_CHAR_LIMIT} chars)")
    print("=" * 60)
    print(text)
    print("=" * 60)
    status = publish(text, date_str=last["date"])
    print(f"Written to: {status['file']}")
    print(f"Bluesky:    {'✓' if status['bluesky_ok'] else '✗'} {status['bluesky_msg']}")
