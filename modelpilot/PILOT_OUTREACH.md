# ModelPilot — design-partner outreach kit

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
>    git clone git@github.com:YOUR_ORG/modelpilot.git
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
