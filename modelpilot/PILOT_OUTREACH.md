# ModelPilot — design-partner outreach kit

Target profile: engineering/platform leader at a company with a real Claude
API bill (≥$2k/mo makes the conversation easy), ideally someone you already
know. The ask is deliberately tiny: a two-week shadow-mode trial on one
service. Nothing about their traffic changes; they get a savings report.

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
