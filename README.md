# Quiet Edge

> *An edge that doesn't shout.*

A multi-strategy **paper-trading** bot for AI infrastructure stocks
(NVDA, AMD, AVGO, MU, TSM, MRVL, ARM, SMCI, SNDK, plus the wider semi /
networking / power / hyperscaler chain — ~50 names total).

Runs unattended on macOS under `launchd`. Monitors Alpaca paper accounts,
executes five strategy sleeves, and pushes daily debriefs to your phone
via [ntfy.sh](https://ntfy.sh). All trades are paper money. The point is
to test, refine, and audit — not to make claims.

- 📊 **What the bot does**: see [Strategy sleeves](#what-it-does) below
- 📈 **What the strategies have produced in backtest**: see [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md)
- 🧪 **Full research findings**: see [research/strategies/FINDINGS.md](research/strategies/FINDINGS.md)
- 📱 **Live paper P&L**: published daily (link coming once 90-day record exists)

> ⚠️ **Paper money only. Not financial advice.** The author is not a
> registered investment adviser. Strategies have been backtested over a
> 2-year AI bull market (2024-2026) and have not yet survived a real
> bear regime in live trading. **Track records from backtests routinely
> fail to replicate live.** Do not point this at a funded account without
> understanding every line. See [BACKTEST_RESULTS.md § Limitations](BACKTEST_RESULTS.md#limitations).

## What it does

Five sleeves sharing a paper $100k:

| Sleeve | Strategy | Capital |
|---|---|---|
| Bull put credit spreads | 20-delta, 5%-wide, 45 DTE, 25% profit target | risk cap $17.5k |
| Trend-following equities | Long when >50-day SMA, 8% stop | $21k |
| Rotational momentum | Top-3 by 10-day return, ~monthly rebalance | $17.5k |
| Earnings straddles | AVGO + MRVL only, T-1 open / T+1 close | $10.5k |
| AI full-chain basket | ~48 names equal-weight, monthly drift rebalance | $17.5k |

Plus: morning consolidated summary, intraday check-ins every 30 min,
close report, EOD debrief, and a daily Claude Code reminder.

## Requirements

- macOS (the launchd bits are Mac-specific; the Python is portable)
- Python 3.12+
- An [Alpaca paper trading account](https://alpaca.markets) (free)
- An [ntfy.sh](https://ntfy.sh) topic + the ntfy app on your phone

## Setup

```bash
# 1. Clone
git clone <repo-url> ~/options-bot
cd ~/options-bot

# 2. Python virtualenv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 3. Credentials — copy and edit
cp .env.example .env
# Fill in:
#   ALPACA_API_KEY / ALPACA_API_SECRET — from https://alpaca.markets dashboard
#                                        (use paper keys, not live)
#   NTFY_TOPIC                          — any unguessable string; subscribe
#                                        to the same topic in the ntfy app

# 4. Smoke test — should print one scan cycle, then Ctrl-C
./venv/bin/python run.py live

# 5. Install as a launchd agent (auto-start at login, restart on crash,
#    wrapped in caffeinate so the Mac doesn't sleep while it's running)
./scripts/install_launchd.sh
```

The launchd installer is idempotent — re-run it any time you change the
plist template or move the bot directory.

## Day-to-day

```bash
# Tail live output
tail -f logs/live.out.log

# See current account snapshot
./venv/bin/python report.py

# Run the EOD debrief manually
./venv/bin/python debrief.py

# Stop / start the agent
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.options-bot.live.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.options-bot.live.plist

# Or, to update after pulling new code, just re-run the installer
./scripts/install_launchd.sh
```

State files live in `logs/` (gitignored):

| File | What |
|---|---|
| `spread_positions.jsonl` | Open + closed bull put spreads |
| `trend_positions.jsonl` | Trend sleeve positions |
| `rotation_positions.jsonl` | Rotational momentum holdings |
| `straddle_positions.jsonl` | Earnings straddle positions |
| `chain_positions.json` | AI full-chain basket snapshot |
| `debriefs.jsonl` | One row per EOD debrief — your historical record |
| `news.jsonl` | Cached Alpaca news feed |
| `live.out.log` / `live.err.log` | Bot stdout/stderr |

## Configuration

All tunables live in `config.py`. Key knobs:

- `STARTING_CAPITAL` — used for lifetime P&L calc in reports
- `SPREAD_AUTO_SUBMIT`, `TREND_AUTO_SUBMIT`, etc. — set `False` to run
  the strategy in alert-only mode (no orders)
- `SPREAD_MAX_TOTAL_RISK`, `*_SLEEVE_CAPITAL` — per-sleeve sizing
- `SPREAD_TARGET_DELTA` — short put delta target (lower = less premium,
  less risk, smoother MtM)

## Working with Claude Code

The `.claude/` directory is checked in — open this repo with Claude Code
and the project context (custom commands, etc.) travels with the clone.
Claude Code can read `logs/debriefs.jsonl` and `logs/live.out.log` to
answer "how are we doing?" / "what happened today?" questions.

## Research

The `research/` directory has the backtest framework and findings
(`research/strategies/FINDINGS.md`). Bulk historical price data lives in
`research/data/` and `research/data_extended/` — both gitignored.
Regenerate with:

```bash
./venv/bin/python research/build_dataset_extended.py
```

## Disclaimer

This software is provided as-is, with no warranty, for educational use.
The author is not a registered investment adviser. Nothing here is
investment advice. Past simulated performance does not predict future
results. **Run it on paper money.**
