# Outlay — the proof, on our own real usage

A short, honest artifact for outreach. Every number below comes from running the
shipped Outlay engine on **real Claude Code usage from building Outlay itself** —
no synthetic data, no cherry-picking. Reproduce it in one command (see bottom).

> Generated 2026-06-20 from `~/.claude/projects` transcripts of this repo's build
> sessions (19–20 Jun 2026). Re-run anytime: `python -m outlay.dogfood --proof-only`.

---

## The headline

On **$340 of real Claude usage**, a naive spend tracker — the kind most teams
build in a spreadsheet or get from a generic dashboard — would report **$2,516**.

| | Reported spend |
|---|---|
| **Outlay (cache-aware, correct)** | **$340.35** |
| Naive token-count tracker | $2,515.52 |
| **Overstatement** | **$2,175 (7.4×)** |

That's not a rounding error. It's a **7.4× difference** on the same usage — large
enough to blow up a budget, a forecast, or a board number.

## Why the gap is real (and why it's bigger the more you scale agents)

The naive mistake is to multiply *all* input-side tokens by the base input rate.
On agentic coding workloads, the model re-sends a large cached prefix every turn,
so **cache-read tokens dominate** — and they bill at ~**0.1×** of base input.

In our real data:

- **98.0%** of input-side tokens were cache reads — **489.5M of 499.7M**.
- Price those at full input rate (the naive error) instead of 0.1×, and the bill
  inflates ~7×.
- The effect *grows* with adoption: the more you lean on prompt caching (the whole
  point of agentic coding), the more wrong the naive number gets.

Per-model, same story:

| Model | Events | Outlay | Naive | Inflation |
|---|---:|---:|---:|---:|
| claude-opus-4-8 | 1,412 | $339.54 | $2,510.86 | 7.4× |
| claude-haiku-4-5 | 119 | $0.81 | $4.66 | 5.8× |

Total: **1,531 billable events** across the two build days.

## What this proves — and what it doesn't

**Proves (on real data):** Outlay costs cache-heavy AI usage *correctly* where the
obvious approach is off by ~7×. Cache-aware, per-token-class costing is the
foundation everything else (attribution, forecasting, budgets) sits on — and it's
the part that's quietly wrong almost everywhere today.

**Does *not* prove here:** ticket-level attribution coverage and forecast accuracy
on *our* repo. We develop on a single rotating branch with squash-merges, so there
are no per-ticket feature branches for the join to resolve — our own workflow can't
exercise that path. Those numbers are:

- **Forecast accuracy** — measured per customer, leave-one-out, on *their* closed
  tickets (the engine reports MdAPE + p90 coverage and never hides the sample size;
  see the in-product "How accurate is this?" page). We quote *your* number, not ours.
- **Attribution coverage** — the make-or-break "% of spend that resolves to a
  ticket," which depends on the customer running normal feature branches (most do).

We'd rather show a real 7× costing gap and be explicit about the rest than dress up
a synthetic accuracy figure.

## How to use this in a conversation

- **Finance / FinOps:** "Your current AI-spend number is probably inflated or
  guessed. On our own usage, the naive method overstated by 7×. Outlay gives you the
  defensible figure — reconciled against the provider invoice — and breaks it down by
  team and project."
- **Eng leadership:** "As you scale Claude Code / Cursor, cache reads become ~98% of
  your tokens. If your dashboard doesn't price token classes separately, your
  per-team and per-engineer numbers are fiction. We get them right, then forecast
  the backlog from them."

## Reproduce it

```bash
# Cost-fidelity proof from local Claude Code transcripts (no repo or token needed):
python -m outlay.dogfood --proof-only            # human-readable
python -m outlay.dogfood --proof-only --json     # machine-readable

# Full real-data run (adds ticket coverage + forecast backtest) on a repo with
# normal feature branches:
GITHUB_TOKEN=… python -m outlay.dogfood --repo owner/name --claude-code ~/.claude/projects
```

Engine: `outlay/proof.py` (`cost_fidelity`), wired into `outlay/dogfood.py`.
Methodology note: the naive baseline is the *charitable* one — it still counts
cache tokens, just at the wrong rate. A tracker that ignores cache tokens entirely
is wrong in the other direction. The point isn't a strawman; it's that on
cache-heavy workloads, the costing model decides the whole number.
