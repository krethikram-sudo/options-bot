# Outlay — demo runbook

How to run the Outlay demos for a prospect call or your own validation. No
install, no dependencies, no API keys for the headline demo — it's stdlib-only
and runs straight from this repo. Python 3.10+.

```bash
cd /path/to/options-bot     # this repo
python3 --version           # need 3.10+
```

---

## Demo 1 — instant (use this on a live call)

Zero setup, runs on bundled demo data, always works.

```bash
# full text report — spend mapped to tickets, coverage, forecast, savings
python3 -m outlay.cli

# + the measured forecast-accuracy backtest (the trust moment)
python3 -m outlay.cli --calibrate

# the VP-ready one-page readout (prints clean to PDF)
python3 -m outlay.cli --html --company "Acme Corp" > readout.html
open readout.html           # macOS → browser → Print → Save as PDF
```

The numbers are illustrative demo data — say so. This is the safest thing to
screen-share: instant, polished, no creds.

## Demo 2 — real data (a prospect's repo, or your own)

Maps actual AI spend to real tickets. Needs a **GitHub token** (read-only) and
local **Claude Code transcripts** (`~/.claude/projects`).

```bash
GITHUB_TOKEN=ghp_xxx python3 -m outlay.dogfood \
    --repo owner/name \
    --claude-code ~/.claude/projects \
    --window-days 30 \
    --html --company "Their Co" > their-readout.html
open their-readout.html
```

Prints **ticket coverage** (the make-or-break metric) + the readout on real
numbers. JSON instead of HTML: swap `--html` for `--json`.

## Demo 3 — the personalization hook (before an email/call)

No spend data needed — measures how *joinable* a prospect's public repos are, so
you can open with a real number about *them*.

```bash
GITHUB_TOKEN=ghp_xxx python3 -m outlay.audit --query "org:theircompany" --max-repos 30
```

> "~75% of your merged PRs tie to an issue — we'd map your AI spend on day one."
This measures the join *precondition*, not their spend. Honest, them-specific.

---

## Driving the live demo (≈3 minutes)

1. `python3 -m outlay.cli` — "AI spend mapped to tickets, with a coverage number."
2. `python3 -m outlay.cli --calibrate` — "and we *measure* forecast accuracy, not
   assert it — here it cut estimate error 66% by conditioning on work size."
3. `open readout.html` — "this one-pager is what you'd get on your real numbers
   in two weeks."

## Getting a GitHub token (demos 2–3)

GitHub → Settings → Developer settings → Personal access tokens →
**Fine-grained token** → read-only on **Contents + Issues + Pull requests**.
Export it for the session: `export GITHUB_TOKEN=ghp_xxx`.

## Output flags (all three entry points)

| Flag | Output |
|---|---|
| *(none)* | human-readable text report |
| `--calibrate` | append the leave-one-out forecast-accuracy backtest |
| `--json` | machine-readable JSON (for a dashboard / CI gate) |
| `--html [--company NAME]` | the VP-ready printable one-pager |

## Gotchas

- **zsh + comments:** macOS zsh doesn't treat `#` as a comment on the command
  line — don't paste trailing `# comments` into the terminal or it errors.
- **Low coverage on a repo?** If it uses `TODO.md` (not GitHub Issues) or its
  agents run detached-HEAD, branch inference returns ~0%. Pick a GitHub-Issues
  repo with PR/ticket hygiene for the cleanest demo. (This is exactly why
  explicit task-tagging exists — see `outlay/VALIDATION.md`.)
- **`open` is macOS-only** — on Linux use `xdg-open readout.html`.
