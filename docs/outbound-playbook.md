# Outlay — Outbound playbook (eng-consumption ICP)

How to find, target, and open the beachhead from `docs/product-strategy.md`: **eng-heavy
software / AI-native companies, 250–5,000 employees, >$250–500k/yr consumption-based AI spend,
multi-provider, with no clear owner.** Founder-led outbound; the goal of every touch is a
15-minute diagnostic call, not a demo.

**The core insight that makes outbound work here:** the pain (AI bill growing 50–100%/yr that no
one can attribute) and our sharpest differentiator (the work-item attribution join) peak in the
*same* accounts. We don't need to create pain — we name a bill they're already nervous about and
offer the one answer they can't get from a dashboard: *what is each team/feature actually costing?*

---

## 1. Targeting — who exactly

**Firmographic filters (the list):**
- **Industry:** software/SaaS, AI-native/ML products, dev-tools, fintech-with-heavy-eng.
- **Size:** 250–5,000 employees; **eng headcount ≥ ~80** (proxy for AI-tool spend at scale).
- **Stage:** Series B–D or profitable scale-up — has a finance function *and* a real bill.
- **Geo:** US first (matches the market analysis + compliance posture).

**Buying-signal filters (rank the list — these predict pain):**
1. **Public AI/LLM usage** — ships an AI feature, or eng blog/conference talk about LLM infra (they have token spend).
2. **Multi-provider footprint** — mentions of Anthropic *and* OpenAI/Bedrock/Azure OpenAI, plus Cursor/Copilot rollouts (the attribution gap is worst here).
3. **Hiring signal** — open reqs for "FinOps," "Platform/Infra eng," or "AI platform" → someone was told to get costs under control.
4. **Funding signal** — raised in last 12 mo → board now asks about burn/efficiency; AI is the fastest-growing line.
5. **Tooling signal** — job posts / stack pages listing Jira/Linear + GitHub (our join lands cleanly).

**Who to contact (two-buyer motion — message both, different angle):**
- **Economic/Finance:** VP Finance, Head of FinOps, CFO (smaller orgs). Angle: *attribution + forecast + budget control.*
- **Technical/Champion:** VP Eng, Head of Platform/Infra, Staff Platform Eng. Angle: *stop being the one who can't answer "what did that cost," metadata-only so no security review.*

**Disqualify before you spend a touch** (from the battlecards): mostly self-hosted GPU on cloud
(ProsperOps fits better), AI spend still trivial (few $20 seats), or no work tracker / no branch
hygiene (our join degrades). Don't burn the account — note and revisit.

---

## 2. The sequence (4 touches over ~12 days, multi-channel)

Keep emails **<120 words**, one ask, no attachments on touch 1, plain text. Personalize the first
line from a *real* signal (their AI feature, a talk, a job post) — never "I came across your company."

### Touch 1 — Email (Day 1) · the named-pain open  — to the technical champion
> **Subject:** what did [their AI feature] cost to run last month?
>
> Hi [First] — saw [specific: "your launch of AI-assisted X" / "the talk on your LLM stack"].
>
> Quick question most platform teams can't answer cleanly: **what did that feature cost in model
> spend last month — and which team drove it?** Provider bills aggregate at the account level, so
> it usually takes a spreadsheet and a guess.
>
> Outlay joins your AI usage to the *work* — ticket → engineer → feature — so the answer is one
> view. **Read-only, metadata-only** (prompts and keys never leave your box, so there's nothing for
> security to clear).
>
> Worth a 15-min look at your own numbers? — [Name]

### Touch 2 — LinkedIn connect + note (Day 3)
> [First] — sent you a note on the AI-cost-attribution problem. We map model spend to the ticket/
> feature/engineer (read-only, metadata-only). Happy to share what it surfaces on a stack like
> yours — no pitch, just the view finance keeps asking eng for.

### Touch 3 — Email reply-in-thread (Day 6) · the proof/forecast angle
> Following up with the part finance cares about: once spend is attributed, we **forecast the
> backlog's AI cost and back-test the error on your own delivered work** — so next quarter's number
> has an error bar, not a finger in the air. And you can put a **program budget** on a body of work
> and get a projected-breach date before month-end.
>
> If [VP Finance/their boss] is feeling the "why is the AI bill up again" conversation, this is the
> 15 minutes that ends it. Open to it this week?

### Touch 4 — Email (Day 12) · the break-up + commitment hook
> Last note, [First]. If you're past ~$250k/yr in model spend, the other lever is **how you pay** —
> committed-spend discounts vs. on-demand. We size that from your run-rate (and flag forfeit risk),
> which is usually 15–30% no one's claimed yet.
>
> If now's not the time, reply "later" and I'll check back next quarter. If it is, here's 15 min:
> [link].

**Finance-buyer variant of Touch 1** (when leading with the economic buyer):
> **Subject:** the AI line nobody can explain
>
> Hi [First] — the fastest-growing line in most software P&Ls right now is model/LLM spend, and it's
> the one finance can't break down by team or initiative (provider bills are account-level totals).
>
> Outlay attributes it to the work — team, feature, engineer — forecasts the next quarter on your own
> history, and lets you set program budgets that flag a breach *before* it happens. Read-only,
> metadata-only.
>
> 15 minutes on your own numbers? — [Name]

---

## 3. The 15-minute diagnostic call (not a demo)
Goal: qualify + create the "I need this" moment with *their* data, then scope a pilot.
1. **(2 min) Frame:** "I'll keep this to 15. Goal is to see if the attribution gap is real for you — if not, I'll say so."
2. **(5 min) Diagnose — ask, don't pitch:**
   - "How many model providers/AI tools are you on now? Who can tell you the per-team split today?"
   - "Last time finance asked 'why is the AI bill up,' how long did the answer take?"
   - "Any budget owner on AI spend, or is it diffuse?"
   - "Roughly what's the monthly run-rate, and how fast is it growing?"
3. **(5 min) Show the one wedge view** (only if qualified): spend → ticket/feature attribution on sample-shaped data, then the program-pacing breach projection. Keep it to the two things they can't get elsewhere.
4. **(3 min) Close to a pilot:** "The honest way to prove this is your own data. A pilot is read-only, metadata-only, ~[X] days to a measured attribution-coverage number and a forecast back-test. Who else needs to be in the room?"

**Pilot definition (the real ask):** read-only connect (tracker + provider usage), N days, deliver
(a) attribution coverage %, (b) a forecast back-test error on their completed work, (c) one program
budget with a projected-breach date. Success = a number they didn't have before. (Gov/regulated runs
the same motion at higher ACV with the compliance posture as the lead — parallel, not the wedge.)

---

## 4. Qualification scorecard (BANT-ish, AI-spend-specific)

| Signal | Strong (pursue) | Weak (deprioritize) |
|---|---|---|
| Monthly model spend | >$20–40k/mo, growing | <$5k/mo, flat |
| Providers/tools | 3+ (multi-vendor gap) | 1, single console suffices |
| Owner | "no one really owns it" | dedicated FinOps already tooled |
| Tracker hygiene | Jira/Linear + branch discipline | no tracker / no branch links |
| Trigger | recent raise, board cost pressure, AI launch | none |
| Hosting | managed APIs (Anthropic/OpenAI/Bedrock/Azure) | self-hosted GPU on cloud (→ ProsperOps) |

3+ "strong" → prioritize. Mostly "weak" → nurture list, revisit next quarter.

---

## 5. Metrics & cadence (founder-led)
- **Volume:** 10–15 *well-researched* accounts/week beats 200 blasted. Personalization is the moat at this stage.
- **Funnel targets to watch:** reply rate (aim ≥8–12% on a tight list), call-booked rate, pilot-start rate, pilot→paid.
- **Instrument the message:** track which open (named-feature-cost vs. finance-line vs. commitment) books calls; double down on the winner.
- **Always disqualify out loud** — telling a bad-fit prospect "you don't need us yet" is the highest-trust move and comes back as referrals.

*Keep every claim in outreach substantiated — coverage % and forecast error are measured on the
prospect's own data in the pilot, never asserted as a benchmark up front.*
