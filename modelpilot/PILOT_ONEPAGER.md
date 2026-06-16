# ModelPilot — cut your Claude bill, pay only for proven savings

*A drop-in proxy that routes each Claude API request to the cheapest model that's
**provably** good enough — measured on your own traffic. You pay only a share of the
savings we actually deliver. Your API key and prompts never leave your environment.*

---

## The offer (zero risk)
- **Free 2-week pilot.** No card to start.
- **You pay only 20% of the savings we deliver.** No savings → no bill.
- **One-line setup**, and a kill switch at every step (revert with the same one line).

## How the pilot works
1. **Sign up** (free): https://modelpilot-console-prod.fly.dev/signup
2. **Point one service at it** — install the ModelPilot client and set
   `ANTHROPIC_BASE_URL` to it. That's the whole integration.
3. **Guidance mode (default):** we *recommend* a cheaper good-enough model per request —
   **nothing about your traffic changes yet.** Your dashboard fills with would-be savings
   and a quality (non-inferiority) read.
4. **Autopilot when you're convinced:** flip it on, ramping from a slice of traffic to all
   of it, with a confidence gate and a **held-out control arm** so every saved dollar is
   *measured*, not estimated.

## What you get
- A **savings report on your own traffic**: per task type, baseline-vs-actual, % bill cut.
- **Quality proof:** a non-inferiority rate (how often the cheaper model held up), plus
  auto-escalation that keeps hard requests on the top model.
- A number you can take to finance — measured, not a marketing percentage.

## Privacy & security (built in)
- **Classification runs locally**; only a task-category label + numeric token counts reach
  us — **never prompt text, model outputs, or your API key.**
- Our endpoints **reject** any payload that looks like it carries prompt/key data (HTTP 422).
- **Fail-open:** if ModelPilot is ever unreachable, traffic passes straight through to
  Anthropic — we can degrade your savings, never your uptime or your data path.
- You keep your own Anthropic account and key (BYOK).

## Pricing
- **Pay-as-you-go:** 20% of realized savings. No fee if we don't save you money.
- **Self-optimize ($99/mo + 15%):** routing tuned to your own traffic for more savings.
- Cancel anytime; one-line revert to the direct API.

## Quick FAQ
- **How much effort?** ~15 minutes — one base-URL change. No rewrite.
- **Will it hurt quality?** Hard requests stay on the top model (quality floor); cheaper
  routes are validated against a control arm, and anything that falls short auto-escalates.
- **Lock-in?** None. Your key, your traffic; revert with one line.
- **What does it cost if savings are small?** Almost nothing — you only pay a cut of what's
  actually saved. If the number's boring, you've spent 15 minutes.

**Estimate first (2 min, no signup, nothing sent):** https://modelpilot.pages.dev/estimator.html
**Start the pilot:** https://modelpilot-console-prod.fly.dev/signup
