# ModelPilot (working name)

**One-liner:** A model-routing copilot for enterprise AI spend. It reads each prompt (and its
conversation context), tells you the cheapest Claude model that will do the job well, optionally
switches the model for you, and proves the savings with statistically honest numbers.

## The problem

Enterprises burn AI budget faster than planned because every request defaults to the biggest,
most expensive model. Most requests don't need it. With current Claude pricing
(June 2026, per million tokens):

| Model | Input | Output | Typical role |
|---|---|---|---|
| Claude Fable 5 (`claude-fable-5`) | $10.00 | $50.00 | Frontier — hardest reasoning |
| Claude Opus 4.8 (`claude-opus-4-8`) | $5.00 | $25.00 | Long-horizon agentic, complex work |
| Claude Sonnet 4.6 (`claude-sonnet-4-6`) | $3.00 | $15.00 | Workhorse — most production tasks |
| Claude Haiku 4.5 (`claude-haiku-4-5`) | $1.00 | $5.00 | Classification, extraction, simple Q&A |

A correctly routed Opus→Haiku request costs ~80% less. Opus→Sonnet, ~40% less. If even a third
of an org's traffic is over-modeled (it's usually more), the savings are a line item the CFO
notices.

## What the product does

1. **Per-prompt model guidance**, based on the prompt text *and* the chat context (conversation
   length, what model handled earlier turns, whether a cached prefix exists, task category).
2. **Two operating modes:**
   - **Advise (Mode 1):** surfaces the recommendation; the user/team takes the action.
   - **Autopilot (Mode 2):** rewrites the model on the request automatically, within
     admin-configured guardrails.
3. **Live savings ticker** in both modes — tokens and dollars saved per request and cumulative,
   computed against a defensible counterfactual baseline.
4. **A results dashboard** that proves value statistically (randomized holdout + counterfactual
   ledger), not just with a vanity number.

## The make-or-break problem

The recommendation must be right. One visible quality regression from a downgrade costs more
trust than a hundred correct downgrades earn. The entire tuning methodology
(`ROUTER_TUNING_PLAN.md`) is built around an asymmetric objective: **never downgrade unless
confident the cheaper model is non-inferior for this prompt; when unsure, do nothing.**

## Docs in this folder

| Doc | Contents |
|---|---|
| `PRODUCT_DESIGN.md` | Architecture, deployment surfaces (API gateway vs. browser extension), Mode 1/Mode 2 mechanics, savings math, the prompt-cache trap, MVP phasing |
| `ROUTER_TUNING_PLAN.md` | How the router gets accurate and stays accurate: golden dataset, LLM-judge labeling, model choices, asymmetric loss, online feedback loop, drift handling |
| `SAVINGS_DASHBOARD.md` | How we prove it: counterfactual ledger, randomized holdout, replay sampling, dashboard views, the monthly CFO report |

## Strategic posture (short version)

- **Start with the API gateway for enterprises** — that's where Mode 2 is technically clean,
  where spend concentrates, and where measurement is airtight. The claude.ai browser extension
  is a Phase-3 companion, not the wedge.
- **Sell with the shadow-mode report:** deploy in advisory/observe-only mode for two weeks, then
  show "here is the $X you would have saved, with zero quality risk taken." The proof artifact
  *is* the sales motion.
- **Defensibility:** Anthropic (or OpenAI) could ship native routing. Our moat is
  (a) cross-provider neutrality (Claude first, OpenAI/Gemini next), (b) enterprise governance —
  per-team policies, audit trails, budget alerts, and (c) the measurement layer — nobody trusts
  the vendor to grade its own homework on savings.
