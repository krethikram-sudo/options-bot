# Outlay — objection handling

Crisp answers to the questions that come up in every customer (and investor)
conversation. Keep them honest — the honesty is the moat. Internal.

---

## 1. "How accurately can you predict our compute spend?" (the #1 question)

**Split it into two questions first** — conflating them kills credibility.

- **Allocating spend that already happened: essentially exact.** Token counts come
  from the provider admin API; we cost them cache-aware (cache reads ~0.1×, writes
  ~1.25× of base input — the thing naive trackers miss by 5–10×). It's arithmetic.
  The only metric here is **coverage** (what % tied to a ticket), which we report
  plainly, unattributed spend reconciled to the invoice.
- **Forecasting future spend: a measured range, not a point.** Per-item cost is
  heavy-tailed (one cheap call vs a 40-turn agentic loop), so we give a **p10–p90
  band**, never a single per-ticket number. But the **aggregate is far more
  predictable** — across a quarter the errors partially cancel (we variance-pool,
  not sum worst cases). Realistic: **single ticket wide; quarter/team ±10–25%** —
  in the spirit of forecasting cloud spend or sprint velocity.

**The close:** "We **backtest the forecast on your own closed tickets** and show
you the median error before you trust it. If it's not good enough on your data,
you see that in week one — we don't hide it. Everyone else quotes a number from
someone else's deployment." Point them to **outlay-ai.com/accuracy**.

**The biggest honest caveat:** non-stationarity. AI usage/dev grew ~18× in under a
year; a fast-scaling team's forecast carries a wider band, and the backtest shows
it. Say this — it builds trust.

## 2. "Isn't this a feature, not a company?"

The **join is a product, not a query** — reliably tying spend to work across
detached-HEAD CI agents, Jira/Linear trackers, and badly-named branches is months
of work (we learned the hard way: naive inference is 0–100% by team). Layer on
cache-aware costing, fidelity tiers, the calibrated forecast, the planned-work
estimator, and proven routing — it's a platform with a natural expansion path
(attribute → forecast → govern → optimize → chargeback), not a dashboard.

## 3. "What if Anthropic / Cursor builds this?"

They're incentivized to grow your spend, not cut it, and each sees only **its own**
tool. Outlay is the **neutral, cross-vendor referee** — the same reason cloud
FinOps (Cloudability, ProsperOps) exists independent of AWS. A vendor grading its
own bill is the conflict of interest we remove.

## 4. "How do you do this without seeing our prompts?"

By architecture. Classification and tagging run **locally on your box**; only
metadata — a task category, token counts, a ticket ID — ever reaches us. Prompt
text, outputs, and keys never leave your environment, and our ingestion endpoints
**reject** any payload that contains them (HTTP 422). It's enforced, not promised.
This is also why prompt-ingesting observability tools structurally can't follow us
into regulated accounts. See outlay-ai.com/security.

## 5. "We could build this ourselves."

Some do — a script that pulls the admin API and charts it. They find the **join is
the hard part** and a one-off dashboard rots. We ship the join with fidelity tiers,
the cache-aware cost model, the calibrated forecast + planned-work estimator, and
proven routing as a product — read-only, metadata-only, free during the pilot. If
it's not worth more than a weekend, build it; if AI is a real, growing line item,
don't maintain it yourself.

## 6. "You're a solo founder / this is early."

True — we're onboarding a small design-partner cohort and you'd shape the roadmap
and pricing. The product is **built and shipped** (attribution, forecast, estimator,
optimization engine with measured savings, live site); the one open thing is proving
it end-to-end on real teams — which is exactly what the pilot does, free. [Pair with
the cofounder/hiring plan as it firms up.]

## 7. "Our branches aren't named after tickets / we're on Jira."

Then passive branch inference alone is low — which is why Outlay's **primary** path
is explicit task-tagging plus the Jira/Linear planner join and PR→issue links, with
branch inference as the zero-config bonus. Detached-HEAD CI agents are recovered via
the PR-branch env and commit trailers. We'll tell you your **real coverage number**
in week one either way.

## 8. "The provider dashboards are already free."

They are — and accurate, per API key and model. The gap is the **join**: a key or
workspace isn't an epic, there's no forecast, no pace guardrail, and no cross-tool
view (Claude Code + Cursor + direct API in one place). Outlay reads those dashboards
read-only and does the attribution, forecasting, budgeting, and routing on top.

## 9. "What does it cost / how do you price?"

A platform fee for attribution + forecasting, plus a **share of the savings** the
optimization engine actually delivers — so we make money when your bill goes *down*.
Design-partner pilots are free; first paid pricing is anchored to the spend we make
visible and reduce (a fraction of it), justified by the pilot's own findings.
