# Premium strategies

This directory is intentionally empty in the open-source repo. Two
strategy sleeves are reserved for paid subscribers:

| Strategy | Backtest Sharpe | What it does |
|---|---:|---|
| **AI full-chain basket** | 4.55 | Equal-weight ~48 names across the full AI value chain (semis + equipment + foundries + networking + optical + storage + servers + power + hyperscalers). Monthly drift-gated rebalance. The highest-Sharpe simple strategy in our 130-test backtest. |
| **Earnings straddles** | n/a* | Selective T-1 / T+1 ATM straddles, restricted to AVGO + MRVL where backtest showed >10% avg earnings move. Captures vol-expansion premium. |

*The straddle sleeve was tested against historical earnings dates separately; see
`research/strategies/FINDINGS.md` for the full methodology.

## How to enable these sleeves

Premium sponsors on [GitHub Sponsors](https://github.com/sponsors/krethikram-sudo)
are automatically added as collaborators on the private companion repo
(`quietedge-premium`). The contents of that repo drop into this `premium/`
directory:

```bash
# After you become a Premium sponsor and accept the GitHub collaborator invite:
git clone https://github.com/krethikram-sudo/quietedge-premium.git /tmp/qe-prem
cp /tmp/qe-prem/*.py ~/options-bot/premium/
# Then restart the bot — it auto-detects the new files at startup
./scripts/install_launchd.sh
```

The public bot detects whether these files are present and runs either
3 or 5 sleeves accordingly. No code changes needed in the public repo.

## What subscribers also get

- Weekly written debrief delivered to email + private Discord
- Private `#premium` Discord channel for setup help and discussion
- Early access to new strategies before they ship to the public repo
- Direct line to the maintainer for setup issues

See [github.com/sponsors/krethikram-sudo](https://github.com/sponsors/krethikram-sudo)
for current subscription tiers and pricing.
