# Outlay — design-partner outreach kit

> **What we're selling now (read this first).** Outlay = **see your AI spend mapped to the work that
> drove it, forecast it by scope, estimate planned work before you build it, and hold it to budget** —
> from **read-only** connections to the tracker and AI-usage data you already have. **Not a proxy, not a
> gateway, no SDK, no app changes.** Prompts, outputs, and your API key **never reach us** — we read
> metadata only. Routing/optimization (the old ModelPilot engine) is **parked**; do **not** pitch
> "route to the cheaper model / pay a cut of savings" — that's the old motion and it confuses the buyer.
>
> **Offer:** a **free, read-only, ~2-week design-partner pilot.** ~30-minute setup (two read-only tokens).
> **No card, no fee** — pilots are free and we're setting early-customer pricing now.
>
> **Links to use:**
> - 2-min estimator / value teaser: **https://outlay-ai.com/#estimate**
> - Product tour (all five capabilities): **https://outlay-ai.com/tour**
> - Request a pilot (in-line form): **https://app.outlay-ai.com/pilot-request**
> - How it works + data handling: **https://outlay-ai.com/docs** · Security: **https://outlay-ai.com/security**
> - Reply-to / inbound: **hello@outlay-ai.com**
>
> Targeting + named prospects live in `PROSPECTS.md` (the list is product-agnostic and still valid —
> Claude-heavy teams with a real, growing, finance-visible bill). Prospect-facing one-pager:
> `OUTLAY_ONEPAGER.md`.

---

## Why now (the timing narrative — lead with this)

A mid-2026 Anthropic billing change (a separate metered pool for agentic usage; a steep effective
increase for heavy users, then a partial walk-back) put AI spend on the CFO's desk. Public bill-shock —
*Uber burned its 2026 AI budget by April; Microsoft's Experiences+Devices org pulled Claude Code over
cost.* The reaction most teams have is "we need to cut it," but they can't even answer the prior
question: **which teams, projects, and tickets is the spend actually going to, and where is it headed
next quarter?** That's Outlay. You don't have to change a line of your stack to get the answer.

**One-line framing:** *"You can't govern a bill you can't break down. Outlay maps your Claude spend to
the work that caused it and forecasts it — read-only, ~30 min, free to get started."*

---

## The 30-second opener (warm DM / email — start here)

> Subject: **where's your Claude spend actually going?**
>
> Hey {name} — saw {company} is building on Claude. Quick one: can you break this month's Claude bill
> down by **team, project, and ticket** — and say what next quarter looks like? Most teams can't, because
> the invoice is one big number.
>
> I built **Outlay**: it connects **read-only** to your tracker + your Anthropic usage and maps every
> dollar to the work that drove it, forecasts the quarter from your open backlog, and even prices planned
> epics *before* you build them. **No proxy, no SDK** — prompts and your API key never touch us, we read
> metadata only.
>
> 30-second teaser: https://outlay-ai.com/#estimate · We're onboarding our first customers free
> (read-only, ~2 weeks). Worth 15 min?

## Cold/warm email (fuller)

> Subject: **your Claude bill, mapped to the roadmap (free design-partner pilot)**
>
> Hi {name},
>
> AI spend at {company} is probably one line on the Anthropic invoice and growing — and when finance
> asks "what's driving it / what's it going to be next quarter," there's no clean answer. That's the gap
> Outlay fills.
>
> Outlay connects **read-only** to two things you already have — your tracker (GitHub Issues / Jira /
> Linear) and your AI-usage data (Anthropic Admin API, Cursor, or Claude Code transcripts) — and gives you:
> - **Spend mapped to ticket, epic, team, and engineer**, reconciled to the invoice.
> - **A forecast for the quarter**, projected bottom-up from your open work, as a range.
> - **Estimates for planned work** — price an epic from its requirements/design docs *before* you build it.
> - **Budgets & pace alerts** by team / project / work-type — *before* overspend, not at month-end.
> - Every forecast **back-tested on your own closed tickets** and shown with the sample size.
>
> The honest part: I don't know your exact numbers yet — that's the pilot. ~30-minute read-only setup,
> ~2 weeks, **free**. Nothing changes in your stack; **prompts, outputs, and your API key never reach us**
> (we're not in the path of your calls — metadata only).
>
> Two-minute look: https://outlay-ai.com/tour · Worth a 15-min call?
>
> {you} · hello@outlay-ai.com

## Community / social post (value-first, then DM)

> If your Claude bill is climbing and you can't say *which projects or teams* are driving it, you're not
> alone — the invoice is one number. You don't need a proxy or a rewrite to fix that: connect your tracker
> + usage data read-only and map spend to the actual work, then forecast the quarter from your backlog.
> (I'm building Outlay, which does exactly this — metadata only, prompts never leave your box. Free
> 2-min teaser: https://outlay-ai.com/#estimate — happy to share more.)

---

## The pilot shape (what you're offering)

1. **Request a pilot:** https://app.outlay-ai.com/pilot-request (in-line form — name, email, the tools
   you use). We reply from hello@outlay-ai.com to schedule a ~30-min setup call.
2. **Connect two read-only sources** on the **Connect** tab:
   - A **tracker** — GitHub Issues, Jira, or Linear (read-only token) → ticket/epic/team metadata.
   - **AI usage** — Anthropic Admin API, Cursor admin, or Claude Code transcripts (read-only) → per-call
     model + token counts + timestamps. **Never prompt content.**
3. **Sync** — on demand or on a daily/weekly schedule. Tokens are encrypted at rest.
4. **See it:** spend mapped to tickets/epics/teams/engineers, the quarter's forecast as a range, a
   worked estimate on a planned epic, and budgets with pace alerts.
5. **Reversible:** read-only tokens; remove Outlay anytime and nothing about your traffic changes — it was
   never in the path.

> Want the whole thing before wiring any keys? The console has a one-click **"See it with sample data"**
> view that fills the dashboard from fixtures (honestly labeled) so a prospect sees the full product on
> the first call.

## Success criteria (agree up front — this is also our validation gap)

| What we prove in the pilot | Target |
|---|---|
| **Attribution coverage** — share of AI spend mapped to a ticket/epic (vs unattributable) | ≥ ~80% of piloted spend, reconciled to the invoice |
| **Forecast accuracy** — leave-one-out back-test on their *own* closed tickets (MdAPE, within-p90) | A real, defensible number with n + coverage shown (no fake precision) |
| **Estimate usefulness** — a planned epic priced with a band finance accepts | A range the team would budget against |
| **Zero footprint** — no proxy, no app change, no prompt/key egress | Verified read-only; security review passes |

> The two numbers that close future customers are **coverage** and a **measured forecast-accuracy figure
> on a real team** — get those from the first 2–3 pilots. That's the whole point of the sprint.

---

## ICP (who to pursue, in order — see `PROSPECTS.md` for named targets)

**Bullseye — the "spend-maturity moment":** a company (Series A–C) with a **real, growing, finance-visible
Claude bill** ($5K–$100K+/mo) and **no one assigned to attribute or forecast it**.

**Buyer — lead with finance (the economic buyer), implement with eng.** Outlay's output is a finance
artifact (COGS attribution, gross-margin-by-product, a board-grade forecast, budget guardrails), so the
person who *feels the pain and owns the budget* is in **finance** — CFO / VP Finance / Head of (Strategic)
Finance / FinOps. They can say "yes, this matters." The only eng involvement is **~30 min to connect two
read-only tokens** (no code change), so qualify with finance, then loop eng to connect. Two exceptions:
at the leanest shops (<~25 ppl) there's often **no finance hire** — the founder/CTO owns the bill, so
target them directly (with the margin framing). And a technically-curious Head of AI / platform lead can
still be a great champion. Finance-persona drafts: `OUTLAY_OUTREACH_BATCH1_FINANCE.md`; eng-persona:
`OUTLAY_OUTREACH_BATCH1.md`. Best results: **multi-thread** finance + eng the same week.

| Priority | Segment | Why Outlay fits |
|---|---|---|
| 1 | Agent platforms / Claude-Code-heavy dev shops (high, bursty, per-ticket burn) | Spend is *naturally per-ticket* → attribution is crisp and the forecast is the roadmap |
| 2 | AI-native SaaS with embedded Claude (support, docs, content) | AI gross margin is a board topic; the per-team/per-feature breakdown lands with finance |
| 3 | Regulated doc pipelines (legal / insurance / healthcare ops) | Audit-minded buyers love metadata-only + a back-tested, defensible forecast |
| 4 | Multi-model teams with a meaningful Claude share | Attribution still works on the Claude slice; quantify the share first |

**Disqualify fast:** <$2K/mo spend (no pain yet); teams that already have mature in-house FinOps mapping
this; anyone wanting model-routing/optimization (that's parked — don't promise it).

**Why our prospect list still applies:** `PROSPECTS.md` targets Claude-heavy teams with a real bill. For
Outlay that's an even cleaner fit — we don't need them to be "routable," only to have a bill they can't
break down or forecast. **Drop the routing narrative; keep the list.**

---

## Mom-Test call script (the first ~10 conversations are validation, not a sale)

Ask about reality before pitching:
1. "What's your Claude bill now — and is it growing?"
2. "If your CFO asked which **teams or projects** drove last month's spend, could you answer today?"
3. "Do you forecast next quarter's AI cost? How — and how close has it been?"
4. "When you plan an epic, do you have any idea what it'll cost in compute before you start?"
5. "Who owns that number internally — and what happens when it's wrong?"
6. *Only then:* show the tour / estimator and offer the free read-only pilot.

Let them tell you whether the pain (can't attribute, can't forecast, surprised by the invoice) is real.

---

## Security FAQ (send when their security reviewer asks)

**Are you in the path of our AI calls?** No. Outlay is **not a proxy or gateway**. Your app calls
Anthropic directly with your key, exactly as today. Outlay reads usage *metadata* on a schedule.

**What do you read?** From the tracker: ticket/epic/team metadata (IDs, titles, status). From AI usage:
per-call model, token counts, timestamps. **Never prompt text, never model outputs, never your API key.**

**What do you store, and how?** The metadata above plus per-request cost figures, in our console. Connector
tokens are **encrypted at rest** (Fernet, keyed off a server secret). You connect with **read-only** tokens.

**Does any PHI / prompt content leave our environment?** No — it physically can't reach us; we're not in
the call path and we don't request bodies. (See the healthcare page for the HIPAA-conscious version.)

**Can we remove it cleanly?** Yes — revoke the read-only tokens; nothing about how your calls are made
changes, because Outlay was never in the path.

**Certifications — the honest part:** the "prompts never leave your environment" guarantee is a property
of the **architecture**. We are **not yet SOC-2 or HIPAA certified** and won't claim what we don't hold.
Need a BAA, a questionnaire, or our roadmap? Email hello@outlay-ai.com — we'll share exactly where we are.

---

## How to run outreach (playbook)

**Posture:** warm-first, value-first, **learn-before-you-sell.** You're a no-name asking for two read-only
tokens — trust is the gate, and the first ~10 conversations are for *validation*, not revenue. The
read-only / metadata-only / no-proxy story makes "yes" nearly free — lead with it.

**Channel order (warmest → coldest):**
1. **Your network + one intro away** — cross `PROSPECTS.md` against everyone you know. Warm intro ≈ 10× a
   cold email.
2. **Bill-shock threads** (HN / r/LLMDevs / r/ClaudeAI / X) — be helpful first (the "you can't govern what
   you can't break down" framing + the free estimator), then DM. Warmest cold audience that exists.
3. **Personalized cold** to Tier-1 buyers (LinkedIn DM + email) — low volume, high personalization.
4. **Communities** — Anthropic Discord / Claude dev forums, same value-first posture.

**Find the buyer:** LinkedIn (Head of AI/ML Platform, VP/Dir Eng, Platform/Infra, FinOps; CTO for smaller
cos) + the GitHub committer of the `@anthropic-ai/sdk` integration. Verify the email pattern; don't spray.

**The ask ladder (lowest friction first):** estimator/tour (self-serve) → 15-min call → free read-only
2-week pilot.

**Cadence:** 8–12 *personalized* touches/day; 1–2 gentle follow-ups, then drop. Log every touch in the
tracker. Target: 5–10 real conversations → 2–3 pilots.

---

## Personalized first-message drafts (verify the person on LinkedIn; swap {name})

*Honest + specific; reference Claude only where confirmed in `PROSPECTS.md`. Insert the tour/estimator link.*

**Chatbase — Yasser Elsaid (founder, lean team = the buyer):**
> Yasser — Chatbase runs a lot of support traffic on Claude, which means your bill is really a pile of
> per-conversation costs you probably can't yet split by customer, feature, or team. Outlay connects
> read-only to your tracker + Anthropic usage and maps the spend to exactly that — plus forecasts next
> quarter from open work. No proxy, prompts never touch us. Free 2-week look: https://outlay-ai.com/tour. 15 min?

**Augment Code — Head of AI / infra lead:**
> Hi {name} — long Claude agent loops make spend naturally per-ticket, but I'd bet you can't see it that
> way today. Outlay maps your Claude usage back to tickets/epics/engineers (read-only, metadata only — no
> proxy, no SDK) and forecasts the quarter from your backlog, so you can answer "what did this project
> cost / what will it" without instrumenting anything. Quick tour: https://outlay-ai.com/tour. Open to 15 min?

**Robin AI — James Clough (CTO) [regulated → lead with privacy]:**
> James — contract review on Claude is high-volume, and finance will want it broken down by matter/team
> and forecast. Outlay does that **read-only and metadata-only** — prompts, outputs, and your key never
> leave your environment (built for exactly your privilege/confidentiality bar), and we're not in the call
> path. Back-tested forecasts on your own closed work, shown with the sample size. Worth 15 min?

**Carta Healthcare / Elation / Commure [PHI → privacy-first]:**
> {name} — for a clinical-data product, the thing that makes AI-spend tooling a non-starter is usually
> data egress. Outlay is built so PHI **can't** reach us: not a proxy, metadata only (token counts, ticket
> IDs), prompts/outputs never leave your environment. What you get is your Claude spend mapped to work and
> forecast by scope — a number you can take to finance. We're not yet HIPAA-certified and won't pretend to
> be; happy to talk BAA/roadmap. 15 min?

**Casey (Tier 3 — Claude UNCONFIRMED → don't assert Claude):**
> {name} — for an insurance-submission product, your LLM spend is spread across extraction/normalization
> work you probably can't yet attribute to a customer or project. Outlay connects read-only to your tracker
> + usage data and maps spend to the actual work, then forecasts it — no proxy, data never leaves your
> environment. Free 2-min teaser: https://outlay-ai.com/#estimate. Worth a quick look?

**Bill-shock thread reply (value-first, then DM):**
> Before deciding how to cut a Claude bill, it helps to see *where it's going* — most teams only have the
> one invoice number. You can map spend to teams/projects/tickets and forecast the quarter without a proxy
> or any app change (read-only on your tracker + usage data). I'm building a tool that does this; free
> estimator if useful: https://outlay-ai.com/#estimate — happy to share more.

---

## Tracking

| Company | Contact (buyer) | Claude confirmed? | ~Monthly spend | Channel | Status | Next step |
|---|---|---|---|---|---|---|
| | | | | | | |

*Statuses: sourced → contacted → replied → call booked → pilot connected → coverage+forecast measured → reference.*
