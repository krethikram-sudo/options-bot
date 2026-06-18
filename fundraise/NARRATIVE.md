# Outlay — fundraising narrative (pre-seed)

The story spine. Everything — deck, one-pager, cold email, the meeting itself —
is a compression or expansion of this. Internal; not for the customer repo.

Stage assumption: **pre-seed, ~$0.5–1.5M.** At this stage VCs fund *team ×
market × wedge × early signal* — not revenue. Our job is to make the wedge
obvious, the "why now" undeniable, and the first proof point real.

`[bracketed]` = founder must insert a real number/fact. Do not ship placeholders.

---

## The one-liner

> **Outlay is the budgeting and cost-control layer for AI engineering spend —
> it maps every dollar of LLM and coding-agent cost to the tickets, epics, and
> roadmap you already plan, forecasts it, and drives it down with proof.**

Alt, sharper for a cold subject line:
> *"What is each epic costing you in AI?" — nobody can answer that. We can.*

## The two-sentence version

Today's tools meter AI spend by infrastructure — API keys, models, dashboards —
so leadership can see the bill exploding but can't answer the question they
actually ask: *what is this body of planned work costing us, and are we on
track?* Outlay attributes every dollar of LLM and coding-agent spend to the work
you already plan, forecasts a quarter from its scope, guards budgets before
they're blown, and then safely routes spend down — turning AI compute from a
runaway line item into something you budget like any other engineering cost.

---

## Problem (the wedge)

AI coding agents (Claude Code, Cursor) went from novelty to daily driver in
~18 months. The AI bill is now a **top-of-mind, fast-growing, finance-visible**
line item — and it's **ungoverned**:

- Spend lives in **provider dashboards** (Anthropic, Cursor admin, OpenAI) keyed
  by API key and model — never by the *work* that drove it.
- No one can answer *"what did this epic/sprint/team cost in AI?"*, forecast next
  quarter from the roadmap, or get warned **before** a team blows its budget.
- Finance sees a number going up and to the right with no levers. Eng leaders get
  asked "why is this so high?" and have no breakdown.

This is the exact gap cloud FinOps filled for compute a decade ago — but AI
coding spend lives in **SaaS invoices and provider APIs, not the cloud bill**, so
the FinOps suites can't see it, and the AI-native tools stop at observation.

## Why now (the part that makes it fundable)

1. **The spend got real.** Coding agents crossed into mainstream daily use; the
   bill crossed the threshold where finance starts asking questions.
2. **The data to do the join now exists.** Provider **admin/usage APIs**
   (Anthropic, Cursor) + tracker APIs (Jira/Linear/GitHub) + agent transcripts
   that carry a git branch — the raw material to tie spend to work — only
   recently all became available.
3. **FinOps-for-AI is nascent, not owned.** The category is forming right now;
   no incumbent owns "AI spend by scope of work."
4. **It's about to get worse (good for us).** More agents, more autonomy, more
   spend per engineer — the governance gap widens every quarter.

## Solution

A platform with four moves, in order of how a customer adopts them:

1. **Attribute** — resolve each AI agent's work (explicit task tag, with git
   branch / PR→issue / Jira-Linear join as complements) back to a ticket → epic →
   roadmap. Cache-aware cost model so the dollars are *right*.
2. **Forecast** — per-task-class cost distributions → bottoms-up forecast of the
   open roadmap, with a *measured* accuracy number (we backtest it, we don't
   assert it).
3. **Guard** — budgets by scope with pace-based alerts that flag a team *before*
   it goes over (not a hard cap that fails you mid-task).
4. **Optimize** — learn per-work-type which cheaper model is *provably* good
   enough (shadow → quality canary → enforce) and route spend down via the
   embedded engine (this is ModelPilot, now a service inside Outlay).

## Wedge → moat → vision

- **Wedge (land):** high-discipline teams already on GitHub Issues get value on
  **day one with zero instrumentation** — the join just fires. (Validated: 60–90%
  joinable where GitHub is the tracker.)
- **Moat (hold):** three compounding defenses incumbents structurally lack —
  1. **The planning-system join.** Gateways/observability/FinOps live at the
     infra layer and can't see tickets/epics. This is the core IP.
  2. **Privacy by architecture.** We attribute and route on **metadata only** —
     prompts, outputs, and keys never leave the customer's environment. The
     observability tools that *could* copy attribution can't, because their whole
     model is ingesting prompts to trace. This unlocks regulated buyers who can't
     use prompt-ingesting tools at all.
  3. **Proven, honestly-measured savings.** A held-out control arm + a
     non-inferiority quality gate means the savings number is audited, not a
     marketing figure — and billing aligns to it (we make money when your bill
     goes *down*).
- **Vision (expand):** the system of record for AI engineering spend —
  allocation, forecasting, budgeting, chargeback, and optimization across every
  AI tool a company uses. The "Datadog/Cloudability for AI labor."

## "Isn't this a feature, not a company?" (rehearse this cold)

The #1 objection. The answer:

- **The join is a product, not a query.** The hard part isn't a dashboard — it's
  reliably tying spend to work across detached-HEAD CI agents, Jira/Linear
  trackers, and teams whose branches aren't named after tickets. We learned this
  the hard way (see VALIDATION.md): naive inference returns 0–100% by team. The
  robust system — explicit tagging + multi-signal fallback + cache-aware costing +
  fidelity tiers — is months of work and the reason a weekend script doesn't
  replace us.
- **Privacy is a structural wedge, not a checkbox.** The incumbents best placed
  to add attribution (LLM observability) can't reach the regulated/sensitive
  segment because they ingest prompts. We're built the opposite way.
- **It's a platform with a natural expansion path** — attribute → forecast →
  govern → optimize → chargeback — each step deepens lock-in, and the optimization
  engine turns a reporting tool into one that pays for itself.
- **"What if Anthropic/Cursor builds it?"** They're incentivized to grow your
  spend, not cut it, and they only see *their own* tool. Outlay is the neutral,
  cross-vendor referee — the same reason cloud FinOps exists independent of AWS.

## What's true today (no overclaiming)

- Product **built and shipped**: attribution, cache-aware costing, forecasting
  with measured calibration, size-conditioned estimates, the optimization engine
  (live measured ~`[40.7%]` savings, 4/5 switches judged non-inferior in a smoke
  test), console + brain deployed, marketing site live at **outlay-ai.com**.
- Mechanism **de-risked on real data**: 6,534 real agent events ingested;
  join-convention audits show 60–90% joinable where GitHub is the tracker.
- **The one open gap:** end-to-end attribution on a real team's live spend —
  i.e., design-partner pilots. This is the thing the raise (and the next 60 days)
  is about. Say it plainly; VCs respect a founder who knows their riskiest
  assumption and is pointed straight at it.

## The ask (fill in)

Raising **$`[1.0]`M pre-seed** to convert a built product into proven traction:
land `[5–8]` design partners → `[2–3]` paying customers → `$[X]`k ARR and the
first `[2]` hires (`[eng, GTM]`) within `[18]` months. `[SAFE / priced]`,
`[target valuation cap]`.
