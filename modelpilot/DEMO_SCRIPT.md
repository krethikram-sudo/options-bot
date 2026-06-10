# ModelPilot — 5-minute demo script

Audience: an engineering leader or platform owner who pays an AI bill.
Setup before the call: terminal in `~/options-bot` with the venv active.
Offline mode (`--offline`) needs no key and no spend — use it anywhere.

## 0:00 — The problem (30 seconds, before touching the keyboard)

> "Every request your teams send defaults to the biggest model. Opus is
> $5-in/$25-out per million tokens; Haiku is $1/$5. Most requests don't need
> Opus — but nobody decides that per-request, so you pay the Opus price on
> Haiku work all day. We route each request to the cheapest model that's
> provably good enough, and — this is the part that matters — we prove the
> savings with a randomized holdout, not vendor math."

## 0:30 — Run it

```bash
python -m modelpilot.demo --offline --fresh
```

Talk over the scrolling decisions:

> "This is a drop-in proxy — one base-URL change, no code changes. Watch the
> decisions: classification and extraction get **switched** to Haiku — 80%
> cheaper. The debugging and refactor prompts **stay** on Opus — we never
> downgrade work that needs the big model. The `advise` rows are below our
> confidence gate, so we *recommend* but don't touch them. And see `control`?
> That's a randomized holdout — we deliberately leave a slice on the default
> model so the savings number is measured, not estimated."

## 2:00 — The summary line

Point at: `REALIZED savings ... POTENTIAL ... (~48% of baseline)`.

> "Realized is what auto-routing actually saved. Potential is what full
> adoption saves. And it's honest accounting: if we ever route wrong and the
> request gets re-run on the big model, that re-run cost is *deducted*."

## 2:30 — The dashboard

Open the printed URL (`/modelpilot/dashboard?days=0`):

- Headline cards → "this is the CFO view."
- Model-mix chart → "traffic migrating from Opus to Haiku/Sonnet over time."
- Quality panel → "negative-feedback rates per arm, escalations visible.
  A system that hides its mistakes can't be trusted about its wins."

## 3:30 — How it gets accurate (the credibility moment)

> "The router is tuned on a golden set: we run real prompts on every model,
> grade the cheap model's answer against the big model's with a
> position-debiased judge, and only auto-route where the false-downgrade rate
> measures under 2%. Today's calibration: near-perfect on classification,
> extraction, translation, Q&A — the highest-volume categories. And it's
> re-calibrated on *your* traffic, not a generic benchmark."

## 4:00 — The ask

> "Zero-risk trial: we deploy in **shadow mode** — your traffic is untouched,
> we just score it. Two weeks later you get a report: 'here's what you would
> have saved, with confidence intervals.' If the number's boring, you've lost
> nothing. If it's not, we turn on advise mode for one team and go from there.
> One base-URL change. Want me to set it up?"

## Objection cheat-sheet

| They say | You say |
|---|---|
| "Our prompts are sensitive" | Shadow mode stores zero prompt text by default; the ledger is token counts and metadata. Capture for tuning is opt-in, sampled, and stays in your tenant. |
| "What if it downgrades something important?" | Confidence-gated, downgrade-only, per-team never-touch policies, and an escalation valve that re-runs failures on the big model and charges the cost against our own savings number. |
| "Anthropic will just build this" | Maybe — but you won't trust the vendor to grade its own savings. We're the independent measurement layer, and we'll cover OpenAI/Gemini next. |
| "Does switching break prompt caching?" | Caches are model-scoped — naive routers lose money here. Our economics layer prices the cache rewrite before every switch and vetoes switches that don't pay. We can show you the math. |
| "What's the catch?" | The router is conservative by design. We leave savings on the table rather than risk quality — the calibration report shows exactly how much, and it improves as it tunes on your traffic. |
