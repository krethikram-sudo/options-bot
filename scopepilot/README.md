# ScopePilot — roadmap-anchored AI spend governance (Phase 0)

Sibling product to ModelPilot. ModelPilot answers *"cheapest model that's good
enough, per request."* **ScopePilot answers *"how much should this body of
planned engineering work cost in AI compute, and are we on track."***

It joins LLM/coding-agent spend to the **work-breakdown units a team already
plans around** — Jira/Linear/GitHub tickets → epics → sprints → roadmap — rather
than to infrastructure tags (API keys, spans, model names) the way every
existing gateway / observability / FinOps tool does. That join is the moat: the
incumbent market lives at the infra layer and structurally can't see the
planning system.

## Why this is differentiated (competitive landscape)

The market has four crowded categories, and **none attribute spend to a unit of
planned work or forecast against the roadmap**:

| Category | Examples | Attributes spend to… | Forecasts roadmap? |
|---|---|---|---|
| AI gateways / routers | Bifrost, LiteLLM, Portkey, ClawRouters, Azure Model Router | virtual key, team | no |
| LLM observability | Langfuse, LangSmith, Braintrust, Helicone, Datadog | span, agent-run, user, feature | no |
| FinOps-for-AI | Finout, Vantage, CloudZero, TrueFoundry, OpenLM | model, team, product, customer | no (reactive alerts) |
| Native vendor admin | Cursor Organizations, Anthropic/OpenAI consoles | seat, team (own tool only) | no |

ScopePilot's three unowned moves: **(1)** the planning-system join
(branch/PR → ticket → epic → roadmap); **(2)** bottom-up forecasting from the
*open* roadmap; **(3)** model-routing recommendations scored **per task-class,
net of rework** (so a downgrade is never recommended when two cheap failures +
an escalation would cost more than one capable run).

## Phase 0 scope (this package)

- **Sources:** Anthropic per-call usage, **Anthropic Admin API** (live puller),
  **Cursor Admin API** (live puller), **Claude Code transcripts** — additive.
- **Planners:** GitHub Issues, **Jira**, **Linear** (`--planner`). Linear
  exposes `branchName` directly; Jira/GitHub join on the key embedded in the
  agent's git branch.
- **Enforcement:** advisory recs compile to a proxy-consumable routing policy
  (`policy.py`, `--emit-policy`) that the ModelPilot gateway can apply.
- **Live shadow loop:** the gateway calls a generic request-observer
  (`scopepilot.shadow:make_observer`) that logs, on real traffic, what each
  `needs_validation` class *would* have cost on the cheaper model — the evidence
  that graduates a class from shadow → enforce.
- **Pipeline:** ingest → cost-normalize → branch→ticket join (fidelity-tiered)
  → task-class classify → attribute → forecast + anomaly guardrails → advisory
  model-routing recommendation.
- **Billing: flat SaaS** (decided). Lead with zero-install, read-only
  attribution; enforcement (reuse the ModelPilot proxy) is a later, optional
  tier — not required to bill.
- **Stdlib-only.** No new dependencies; the live pullers use `urllib` behind a
  transport seam so they're testable offline with no credentials.

## Ingestion sources & fidelity ceiling

Different sources can reach different join fidelity — surfaced honestly so a
number is never trusted beyond what produced it:

| Source | Carries git branch? | Fidelity ceiling | Role |
|---|---|---|---|
| Claude Code transcripts (`gitBranch`) | yes | `branch` (ticket-level) | primary join |
| ScopePilot proxy metadata (tagged) | yes | `call` (ticket-level) | primary join |
| Anthropic Admin API (aggregated) | no | `team` (key→user→team) | invoice reconciliation |
| Cursor Admin API (per-user) | no | `team` (user→team) | per-engineer rollup |

Live pulls via clients in `scopepilot.ingest`, all behind a `urllib` transport
seam (offline-testable, no new deps): `AnthropicAdminClient` /
`CursorAdminClient` (usage), `JiraClient` / `LinearClient` (planners, env-keyed
`JIRA_*` / `LINEAR_API_KEY`). The CLI consumes their JSON so it stays
offline-friendly.

## Enforcement & the graduation loop

`policy.py` compiles recommendations into a gated routing policy
(`--emit-policy policy.json`); `validated` classes ENFORCE, `needs_validation`
classes SHADOW. `shadow.py` is the live half:

1. The ModelPilot gateway exposes a **generic, product-agnostic** request-
   observer seam (`MODELPILOT_REQUEST_OBSERVER="module:factory"`) — it takes no
   dependency on ScopePilot and can never alter or block a request.
2. ScopePilot registers `scopepilot.shadow:make_observer`. On each request the
   gateway hands it a small payload (decision + token usage + the work
   branch/ticket from `x-modelpilot-work-*` headers); the observer resolves the
   task-class and appends a delta to the shadow log: *what this request cost on
   the model it ran, vs. what the candidate would have cost.*
3. `graduation_report()` aggregates the log; once a class has enough live
   counterfactuals it's `ready_for_canary`. Promotion to ENFORCE still requires
   an independent quality check — `promote()` only flips classes you've
   validated. **Cost evidence accrues automatically; quality is never assumed.**

```
export MODELPILOT_REQUEST_OBSERVER=scopepilot.shadow:make_observer
export SCOPEPILOT_POLICY=policy.json SCOPEPILOT_ISSUES=issues.json
export SCOPEPILOT_PLANNER=github SCOPEPILOT_SHADOW_LOG=shadow.jsonl
```

## Run it

```bash
python -m scopepilot.cli                 # demo report over bundled fixtures
python -m scopepilot.cli --window-days 9 # project observed spend to a monthly figure
python -m scopepilot.cli --usage usage.json --issues issues.json   # real exports
```

## What it proves (Phase 0 exit bar)

On one team's history, the attributed total reconciles to the provider invoice
within a stated tolerance, and the report surfaces ≥1 model-downgrade
recommendation an eng lead agrees is real. The bundled fixtures demonstrate all
of it: 98% ticket coverage, every fidelity tier, an anomaly ticket flagged at
11.5× its class median, a forecast that *declines to cost* an item whose class
has no history, and one `validated` + several `needs_validation` routing recs.

## Design notes (the honesty layer)

- **Fidelity is first-class.** Every attributed dollar carries a tier —
  `call` > `branch` > `team` > `invoice`. A finance owner trusts "team-level,
  ±15%"; a confident per-ticket number that's secretly a guess loses the room.
  The report leads with the fidelity breakdown for exactly this reason.
- **Cache tokens are costed separately.** Cache reads bill ~0.1× and writes
  ~1.25× of base input. Collapsing them into base-rate input — the most common
  naive-tracker bug — overstates cached agentic workloads 5–10×.
- **Guardrails bind on outliers, not every task.** Per-task hard caps are a
  trap: a cap that binds one iteration before success means you pay and get
  nothing. We flag tickets ≥N× their class median instead.
- **Forecasting is per task-class, never per ticket.** A single unseen ticket
  is as unpredictable to cost as it is to estimate in hours; the distribution
  over a *class* is stable and useful.
- **You never enforce a downgrade you haven't proven.** `validated` recs
  (cheaper tier seen in history) compile to `ENFORCE`; `needs_validation` recs
  run in `SHADOW` — logged, traffic unchanged — until their own data graduates
  them. The policy composes with ModelPilot's category floors as
  `binding_floor = min(category_floor, class_floor)` for enforced classes, with
  ModelPilot's brittle-call guard still vetoing on top, so a lowered floor can
  never break a structured-output/tool call.

## Module map

| Module | Responsibility |
|---|---|
| `models.py` | `UsageEvent`, `WorkItem`, `Attribution`, `FidelityTier`, `TaskClass` |
| `pricing.py` | model rate table (incl. cache economics) → `cost_usd()` |
| `ingest/anthropic_usage.py` | Anthropic per-call usage JSON → `UsageEvent`s |
| `ingest/anthropic_admin.py` | live Admin Usage API puller + report parser |
| `ingest/cursor.py` | live Cursor Admin API puller + events parser |
| `ingest/claude_code.py` | Claude Code `.jsonl` transcript parser (branch-level) |
| `ingest/github_issues.py` `ingest/jira.py` `ingest/linear.py` | planner JSON → `WorkItem`s |
| `join.py` | **the IP** — branch→ticket join + identity graph + fidelity tiers |
| `classify.py` | task-class heuristics (labels → branch verbs → diff size) |
| `attribute.py` | orchestrates join+cost; per-ticket rollups + coverage |
| `forecast.py` | per-class distributions, roadmap forecast, anomaly flags |
| `recommend.py` | per-class routing recs, scored net of rework |
| `policy.py` | **enforcement** — gated routing policy for the ModelPilot proxy |
| `shadow.py` | **live loop** — gateway observer, shadow ledger, graduation |
| `report.py` / `cli.py` | the 30-second VP-readable report + `--emit-policy` |

## Deferred to later phases (deliberately not in P0)

SSO/SCIM-fed identity graph; a learned task-class model; budget-vs-actual
burndown per epic; an automated canary harness that runs the candidate model on
a sampled fraction (the quality half of graduation); non-Anthropic provider rate
tables (GPT/Gemini). The integration surface (N providers × M planners) is the
treadmill *and* the moat — prioritized by what design partners actually use.

## Settled decisions

1. **Billing model — flat SaaS.** Land with zero-install read-only attribution;
   the enforcement proxy is an optional later tier, not a billing prerequisite.
2. **Ingestion sources — all four shipped** (Anthropic per-call + Admin API,
   Cursor, Claude Code). Claude Code is the branch-bearing primary join; the
   admin APIs reconcile to invoice.
3. **Planners — GitHub, Jira, Linear shipped** (parsers + live API pullers).
4. **Enforcement — shipped, gated.** `policy.py` compiles recs into a proxy
   policy; only `validated` classes enforce, `needs_validation` runs in shadow.
5. **Live shadow loop — shipped.** Gateway observer seam + `shadow.py` log
   real-traffic counterfactuals and report graduation readiness.
