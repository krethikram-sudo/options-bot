# ModelPilot — design-partner outreach kit

> **2026-06-16 REFRESH (use these — sections further below predate the shadow-mode
> removal + the hosted console).** Current motion: **estimator-led, hosted-console
> signup, Guidance→Autopilot (no "shadow"), pay-on-realized-savings.** Target the
> **spend-maturity moment** (a real, growing, finance-visible Claude bill, no one
> minding it). See `ICP.md` + `GTM_PLAN.md` (bill-shock motion). Prospect-facing
> one-pager: `PILOT_ONEPAGER.md`.

## The 30-second opener (warm DM / email — start here)
> Subject: **cut your Claude bill — only pay if it works**
>
> Hey {name} — saw you're building on Claude. I built **ModelPilot**: it routes each
> request to the cheapest model that's actually good enough, **proves the savings on
> your own traffic** (held-out control arm), and you **pay only a cut of what we save
> — no savings, no bill.** Setup is a one-line base-URL change; your API key and
> prompts never leave your environment.
>
> 2-min gut check before anything → {estimator link: https://modelpilot.pages.dev/estimator.html}
> (paste your spend, see a rough number — nothing's sent anywhere).
>
> Worth 15 min to run it on your real traffic for two weeks, free?

## Cold/warm email (fuller)
> Subject: **proof, not promises: what routing would cut off your Claude bill**
>
> Hi {name},
>
> Most teams send everything to the flagship Claude model out of caution and overpay —
> a quality regression gets blamed on the engineer; a 3× bill is invisible. ModelPilot
> fixes that safely: it routes each request to the cheapest model that's *provably good
> enough*, keeps your hard tasks on the top model, and **measures the savings against a
> held-out control arm on your own traffic** — so the number is real, not a marketing %.
>
> Honest pitch: I don't know what it saves *you* yet — that's the pilot. Two weeks, a
> one-line setup, your key/prompts never leave your box. You get a report: savings per
> task type, baseline-vs-actual, and the quality analysis. **You pay only 20% of the
> savings we actually deliver — if it's boring, you owe nothing.**
>
> Rough estimate in 2 min: {estimator link}. Worth a 15-min call?
>
> {you}

## Community / social post
> Your Claude API bill bigger than you'd like? I built a drop-in that routes each
> request to the cheapest model that's good enough and **proves** the savings on your
> own traffic — you pay only a cut of what it saves (no savings, no bill), and your
> prompts never leave your environment. Free 2-min estimator (no signup, nothing sent):
> {estimator link}. Happy to run a free 2-week pilot on real traffic — DM me.

## The pilot shape (what you're offering)
1. **Sign up** (free, no card): {signup: https://modelpilot-console-prod.fly.dev/signup}.
2. **One-line setup:** install the ModelPilot client, point your service's
   `ANTHROPIC_BASE_URL` at it. Key never leaves; prompts never leave.
3. **Guidance mode (default):** we *recommend* the cheaper-but-good-enough model per
   request — nothing about your traffic changes yet. The dashboard fills with
   would-be savings + a quality (non-inferiority) read.
4. **Autopilot when convinced:** flip it on, ramping from a slice of traffic → all,
   with a confidence gate + held-out control arm so every claimed dollar is measured.
5. **Kill switch at every step** — revert to the direct API with the same one-line change.

## Success criteria (agree up front)
- Measured potential savings ≥ ~20% of baseline on piloted traffic.
- Quality: non-inferiority parity vs the control arm (no detectable regression).
- Zero gateway-caused incidents; negligible added latency (routing decision is local).
- The honest test: after seeing real numbers, would they pay the 20%?

---


## ICP (who to pursue, in order)

**Bullseye:** engineering-led product companies (Series A–C), **$5K–$100K/mo
Claude API spend**, traffic that is mixed-difficulty defaulting to an
expensive model. Buyer = CTO / founding engineer / platform lead **who sees
the Anthropic invoice and can change a base_url without a meeting**.

| Priority | Segment | Why it fits |
|---|---|---|
| 1 | AI customer-support products/teams (triage, drafting, summarization) | Highest volume, ~70% Haiku-able, quality measurable via CSAT/escalations; calibration shows our best categories |
| 2 | Document pipelines (legal/insurance/compliance/healthcare ops) | Extract/classify/summarize mix; audit-minded buyers love the proof artifact |
| 3 | SaaS with embedded Claude assistants | AI gross margin is a board topic; CFO report lands |
| 4 | Agent platforms / Claude Code-heavy dev shops | High burn but conservative routing — pitch headroom + smaller %, second wave |

**Disqualify fast:** large enterprises (no SOC2/SLA yet), multi-provider
shoppers (OpenRouter/Martian's customers), <$2K/mo spend,
latency-hypercritical real-time paths, teams behind another gateway (unless
via the advisory-API sidecar path).

**Sourcing:** Anthropic "powered by Claude" showcases; job posts mentioning
the Claude API; Anthropic Discord / Claude dev communities; YC support- and
doc-AI companies; public complaints about Anthropic bills or rate limits;
and above all, warm contacts matching the profile — personal trust
substitutes for the case studies a beta doesn't have yet.

Target profile detail and the ask below.

Target profile: engineering/platform leader at a company with a real Claude
API bill (≥$2k/mo makes the conversation easy), ideally someone you already
know. The ask is deliberately tiny: a two-week shadow-mode trial on one
service. Nothing about their traffic changes; they get a savings report.

## Beta-access reply (send when someone requests access)

> Subject: **ModelPilot beta — your access**
>
> Great to have you in the beta! Two quick things to get you going:
>
> 1. **Reply with your GitHub username** (and any teammates') — I'll add you
>    to the private repo. You'll get an invite email from GitHub; accept it
>    and you're in.
>
> 2. Once you have access, the two-minute proof (no API key, no spend):
>
>    ```
>    git clone git@github.com:krethikram-sudo/modelpilot.git
>    pip install -e modelpilot
>    modelpilot demo --offline
>    ```
>
>    Then the real thing — shadow mode, zero risk, one line in your app:
>
>    ```
>    modelpilot gateway --mode shadow --port 8400
>    # your app: ANTHROPIC_BASE_URL=http://localhost:8400  (key stays yours, never stored)
>    ```
>
>    After a day of traffic, `http://localhost:8400/modelpilot/dashboard`
>    shows what routing would have saved you.
>
> Happy to do a 30-minute setup call instead — usually faster, and we can
> agree what a successful trial looks like for you up front. A few times
> that work for me: {slots}.
>
> Updates ship to the repo automatically (`git pull` + CHANGELOG.md);
> feedback via GitHub issues or just reply here. Welcome aboard!

Then: add them as a **read-only collaborator** (repo → Settings →
Collaborators), log them in `pilot_tracker.csv` as `shadow` once installed,
and follow the GTM_PLAN.md pilot runbook (day-3 check, week-1 report).

## Cold/warm intro email

Subject: **Cut your Claude bill ~30-50% — measured, not estimated (2-week free look)**

> Hi {name},
>
> I'm building ModelPilot — a drop-in proxy for the Claude API that routes
> each request to the cheapest model that's provably good enough for it
> (Haiku is 80% cheaper than Opus; most traffic doesn't need Opus).
>
> The honest version of the pitch: I don't know what it saves *you* yet —
> that's the point. We deploy in shadow mode (one base-URL change, your
> traffic completely untouched, no prompt text stored), and two weeks later
> you get a report: "here's what routing would have saved, per team and per
> workload, with the quality analysis to back it."
>
> If the number is boring, you've spent 15 minutes on a config change. If
> it isn't, you'll have the data to decide what to do about it.
>
> Worth a 20-minute call? I'll demo the live routing + dashboard.
>
> {you}

## Follow-up after the demo

> Quick recap of the trial shape:
>
> 1. You point one service's `ANTHROPIC_BASE_URL` at the gateway
>    (your infra or ours — your call; most start self-hosted).
> 2. Shadow mode for 2 weeks: zero behavior change, zero prompt storage.
> 3. You get the would-have-saved report + dashboard access.
> 4. If you like the numbers: advise mode (headers only) on one team,
>    then auto-routing with a confidence gate calibrated on your traffic
>    and a randomized holdout so every claimed dollar is measured.
>
> Kill switch at every stage; you can revert to direct API with the same
> one-line change.

## Security FAQ (send when their security person asks)

**What does the gateway see?** Request/response bodies in transit (it's a
proxy), exactly like any API gateway you already run. It forwards your
existing API credentials and never stores them.

**What does it store?** By default: token counts, model names, routing
decisions, timestamps, a hashed session key. **No prompt text, no response
text, no API keys.** Prompt capture for router tuning is opt-in
(`MODELPILOT_CAPTURE_PCT`, default 0), sampled, and stays in your deployment.

**Where does it run?** Self-hosted in your VPC for the pilot — it's a
single Python service with a SQLite/Postgres ledger. Nothing leaves your
network except the API calls you were already making to Anthropic.

**What can it change?** In shadow and advise modes: nothing, structurally —
requests pass through byte-identical. In autopilot: only the `model` field,
only downward in cost, only above a measured confidence threshold, and
never for routes on your never-touch list.

**Blast radius if it dies?** It's in your request path, so: health-checked,
and the client falls back to the direct API base URL on connection failure
(standard SDK retry config). Pilot deployments start on non-critical paths.

## Pilot success criteria (agree these up front)

| Metric | Target |
|---|---|
| Shadow report: potential savings | ≥20% of baseline spend on piloted traffic |
| Added p95 latency through gateway | ≤25ms (shadow; routing decision is local) |
| Incidents caused by gateway | 0 |
| (If advancing to autopilot) RCT quality parity | regenerate/escalation rates statistically indistinguishable from control |

## Tracking

| Company | Contact | Status | Monthly Claude spend | Next step |
|---|---|---|---|---|
| | | | | |

---

## How to run outreach (2026-06-16 — playbook)

**Posture:** warm-first, value-first, **learn-before-you-sell.** You're a no-name asking
people to touch their API traffic — trust is the gate, and the first ~10 conversations are
for *validation*, not revenue.

**Channel order (work warmest → coldest):**
1. **Your network + 1 intro away** — cross the prospect list against everyone you know. A warm
   intro converts ~10× a cold email and clears the trust barrier. Start here.
2. **Bill-shock threads** (HN / r/LLMDevs / r/ClaudeAI / X) — **be helpful first** ("you don't
   have to leave Claude, route the cheap 60–80%; free estimator → {link}"), then DM. Warmest cold
   audience that exists — they have the pain today.
3. **Personalized cold** to Tier-1 buyers (LinkedIn DM + email). Low volume, high personalization.
4. **Communities** — Anthropic Discord / Claude dev forums (same value-first posture).

**Find the buyer:** LinkedIn (CTO / Head of AI / platform lead; for small cos the founder/CTO) ·
the GitHub committer of the `@anthropic-ai/sdk` integration · infer + **verify** the email pattern
(Hunter/Apollo) — verify, don't spray.

**The ask ladder (lowest friction first):** estimator (2 min, self-serve) → 15-min call → 2-week
free pilot (Guidance → measure → Autopilot).

**Disarm the trust objection up front:** "your API key and prompts never leave your environment,"
and offer to **start in Guidance mode (recommend-only — nothing changes).** Makes "yes" nearly free.

**Mom-Test call script (the first 10 are validation):** ask about reality before you pitch —
1. "How big is your Claude bill now — and is it growing?"
2. "Who owns that cost? Has anyone been told to cut it?"
3. "Have you tried to optimize it? What happened / why not?"
4. "What would 'too risky to try' look like for you?"
5. *Only then:* show the estimator + offer the pilot.
Let them tell you whether the pain is real. That's the whole point of the sprint.

**Cadence:** 8–12 *personalized* touches/day; 1–2 gentle follow-ups, then drop; log every touch in
`pilot_tracker.csv`. Target: 5–10 real conversations → 2–3 pilots.

## Personalized first-message drafts (copy, then verify the person on LinkedIn)
*Honest + specific; reference Claude only where confirmed. Swap {name}; insert the estimator/one-pager.*

**Chatbase — DM/email to Yasser Elsaid (founder; lean team = he's the buyer):**
> Yasser — Chatbase running support chatbots on Claude at your volume almost certainly has a big
> chunk of traffic (intent classification, FAQ, summarization) that a cheaper model handles just as
> well. I built ModelPilot: it routes those to the cheapest good-enough model, **proves** the savings
> on your own traffic (held-out control arm), and you pay only a cut of what we save — key/prompts
> never leave your box. 2-min estimate: {estimator}. Worth 15 min?

**Augment Code — LinkedIn to the Head of AI / infra lead:**
> Hi {name} — long agent loops on Claude Sonnet burn a lot of tokens, and a real share of the
> sub-steps (planning, file reads, simple edits) don't need a frontier model. ModelPilot routes the
> cheap ones down with a quality floor + control-arm proof, so you keep Devin-grade quality on the
> hard stuff and stop overpaying on the rest. You pay only 20% of what we actually save. Quick
> estimate: {estimator}. Open to a 15-min look?

**Robin AI — email to James Clough (CTO) [regulated → lead with privacy]:**
> James — contract review on Claude means a lot of high-volume first-pass work (clause
> classification, extraction) running on a top model. ModelPilot routes that to the cheapest
> good-enough model and **proves quality held** on your own traffic — and because classification
> happens locally, **prompts and your key never leave your environment** (built for exactly your
> privilege/confidentiality bar). Pay only a share of realized savings. 15 min?

**Casey (Tier 3 — Claude UNCONFIRMED → pitch routing on merits, do NOT assert Claude):**
> {name} — for an insurance-submission product, a lot of the LLM work (field extraction,
> normalization) is routine enough for a cheaper model. ModelPilot routes each request to the
> cheapest model that's *provably* good enough, measured on your own traffic, and you pay only a cut
> of the savings — no savings, no bill. One-line setup, your data never leaves your environment.
> Worth a quick look? Free estimate: {estimator}.

**Bill-shock thread reply (value-first, then DM):**
> You don't have to rip Claude out to fix this — most of the spend is the cheap 60–80% of calls
> going to the flagship model. Route those to a good-enough cheaper model with a quality floor and
> you keep the hard stuff on top. (I'm building a tool that does this + proves the savings on your
> own traffic; free estimator if useful: {estimator} — happy to share more.)
