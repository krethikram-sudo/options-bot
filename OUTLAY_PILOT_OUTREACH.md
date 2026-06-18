# Outlay — design-partner pilot kit

The one validation gap left is **end-to-end ticket coverage on a real team**.
This is the kit to land the first 3–5 design partners that close it. Sending is
yours; everything you need to send is here.

## Who to target (ICP)
From the join-convention audit, the teams where Outlay works on day one are the
**high-discipline cluster** (70–100% of merged PRs tie to a ticket):

- **Engineering org of ~20–150**, building real product (not an OSS list/repo).
- **Uses a tracker with hygiene** — GitHub Issues / Jira / Linear, with a
  PR-template or "Closes #" convention. (If they're on Jira/Linear, even better —
  that's the enterprise wedge incumbents can't see.)
- **Runs AI coding agents at real spend** — Claude Code and/or Cursor in daily
  use; an AI bill that's now finance-visible and growing.
- **Has a person feeling the pain** — a VP/Director of Eng who owns delivery *or*
  a FinOps/finance lead watching the line item climb.

Disqualifiers: solo founders, agencies, teams with no tracker discipline, teams
whose AI spend is still trivial.

## Where to find them
1. **Warm network first** — anyone you know in eng leadership at a Claude-heavy
   shop. One intro beats fifty cold emails.
2. **Signal-based cold** — people posting about AI coding-tool spend, "Cursor
   bill," "Claude Code at scale," FinOps-for-AI; companies hiring "FinOps" or
   "platform/DevEx" roles; Anthropic/Cursor case-study customers.
3. **Communities** — eng-leadership Slacks/Discords, r/ExperiencedDevs,
   FinOps Foundation channels, Claude/Cursor power-user threads.

## What the pilot is (offer)
A **2–3 week, read-only** engagement, free for design partners:
- **They connect:** one tracker (GitHub/Jira/Linear) + their AI usage (Claude
  Code transcripts, Cursor admin export, and/or the Anthropic admin API).
  Read-only. **Prompts never leave their environment** — Outlay runs on
  metadata (categories, token counts, ticket IDs).
- **They get back:** their real AI spend mapped to tickets/epics/teams, a
  ticket-coverage number, a quarter-forecast from their open scope, a budget
  burndown with pace guardrails, anomaly flags, and an optimization-savings
  estimate.
- **Success criteria (agree up front):** ticket coverage ≥ 60%, at least one
  actionable finding (an over-pace epic or a real downgrade opportunity), and a
  forecast the eng lead finds credible.
- **In exchange:** candid feedback, a reference if it lands, and influence over
  the roadmap and pricing.

## One-paragraph pitch (paste into emails)
> Outlay turns AI compute from an unpredictable line item into something you
> budget like any other engineering cost. It attributes every dollar of LLM and
> coding-agent spend to the work you already plan — tickets, epics, roadmap —
> then forecasts cost by scope and flags a team before it blows its budget.
> Read-only, prompts never leave your environment. We're onboarding a small
> design-partner cohort and I'd love to map your real AI spend to your roadmap in
> a couple of weeks, free.

## Email templates

### A. Warm intro (via a mutual)
> Subject: mapping AI spend to the roadmap — quick one
>
> Hi {name} — {mutual} thought we should talk. I'm building **Outlay**: it maps
> AI/coding-agent spend to your tickets and epics, forecasts a quarter from its
> scope, and flags teams before they go over budget. Read-only, prompts stay in
> your environment.
>
> We're taking on a few design partners. Could I map your real AI spend to your
> roadmap in ~2 weeks (free) and show you the ticket-level picture? 20 min this
> week to see if it's a fit?

### B. Cold → eng leader
> Subject: what is each epic costing you in AI?
>
> Hi {name} — you're shipping a lot with Claude Code/Cursor. Quick q: do you know
> what each **epic or sprint** is costing you in AI, and which work is about to
> blow its estimate? Most teams can't answer that — the spend lives in API
> dashboards, not against the roadmap.
>
> **Outlay** maps it to your tickets and forecasts by scope. I'm onboarding a few
> design partners — read-only, prompts never leave your env, free for the pilot.
> Worth 20 minutes to see your real numbers?

### C. Cold → finance / FinOps
> Subject: governing the AI line item by scope of work
>
> Hi {name} — AI compute is probably your fastest-growing, least-predictable line
> item. **Outlay** allocates it to teams, cost centers, and roadmap items, sets
> budgets by scope, and alerts you *before* overspend — not at month-end.
>
> We're running a small design-partner cohort (read-only, content never leaves
> your environment, free). Could I show you your real AI spend allocated to the
> work that drove it? 20 minutes this week?

## Pilot agreement (lightweight outline)
- **Scope:** read-only access to {tracker} + {AI usage source}; 2–3 weeks.
- **Data:** metadata only (categories, token counts, ticket IDs); no prompt
  content or keys leave their environment; deleted on request at pilot end.
- **Deliverable:** attribution + coverage %, forecast, burndown, savings estimate.
- **Cost:** free for design partners.
- **Mutual:** they give feedback + (if it lands) a reference; you give roadmap
  influence and early pricing.
- NDA optional/mutual if they want one.

## Track it
Keep a simple sheet: company · contact · ICP-fit · source · stage
(contacted → call → connected → coverage% → outcome). The **coverage %** column
is the one that matters — it's the metric the whole bet turns on.
