# Contributing to Quiet Edge

Thanks for your interest. This is a small project run by a single maintainer.
Contributions are welcome, but please read this first.

## Before you open an issue

- **Setup problems**: re-read [`README.md`](README.md). Most issues are an
  unset env var, a missing Python version, or a misconfigured launchd plist.
- **Strategy questions**: read [`BACKTEST_RESULTS.md`](BACKTEST_RESULTS.md)
  and [`research/strategies/FINDINGS.md`](research/strategies/FINDINGS.md).
  The "why" of every strategy is documented there.
- **Disclosure**: the live paper bot's actual P&L is published daily on
  [Bluesky](#) (link coming soon — first 90 days needed). Don't ask for
  signals or trade advice in issues.

## Good issue types

- Bug reports with a clear repro (stack trace + minimal example)
- Documentation gaps (you tried to do X and the README didn't help)
- Strategy proposals with backtest code/results attached
- Broker-abstraction PRs (IBKR, Tradier, etc.) — the bot is Alpaca-only today

## Bad issue types

- "Will this make me money?" — read the disclaimer
- "Can you add Strategy X?" with no implementation — open a discussion instead
- Requests for personalized trading advice — not happening, ever

## Pull requests

- Keep them small and focused. One PR, one concern.
- Add tests where it makes sense. The `research/` directory has the backtest
  framework — strategy changes should come with a backtest run.
- Don't reformat unrelated code in your PR. Run `python -m py_compile` on
  changed files; that's the bar.
- By contributing you agree your changes are MIT-licensed.

## Code of conduct

Don't be a jerk. Don't post other people's PII. Don't share trading API keys
or credentials in any form. We'll close issues and bans without warning.

## Maintainer response time

This is a side project. Expect responses within a few days, not hours.
Sponsors at the Premium tier (via [GitHub Sponsors](https://github.com/sponsors/krethikram-sudo),
when launched) get priority response in a private Discord — that's part of
what they pay for.
