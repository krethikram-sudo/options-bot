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

- **Provider:** Anthropic usage (per-call `usage` object + admin export shape).
- **Planner:** GitHub Issues (issues/PRs + branch links).
- **Pipeline:** ingest → cost-normalize → branch→ticket join (fidelity-tiered)
  → task-class classify → attribute → forecast + anomaly guardrails → advisory
  model-routing recommendation.
- **Read-only.** No proxy/enforcement dependency — a flat-SaaS-friendly land
  motion. Enforcement (reuse the ModelPilot proxy) is a later tier.
- **Stdlib-only.** No new dependencies; runs anywhere Python 3.11 does.

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

## Module map

| Module | Responsibility |
|---|---|
| `models.py` | `UsageEvent`, `WorkItem`, `Attribution`, `FidelityTier`, `TaskClass` |
| `pricing.py` | model rate table (incl. cache economics) → `cost_usd()` |
| `ingest/anthropic_usage.py` | Anthropic usage JSON → `UsageEvent`s |
| `ingest/github_issues.py` | GitHub issues/PR JSON → `WorkItem`s |
| `join.py` | **the IP** — branch→ticket join + identity graph + fidelity tiers |
| `classify.py` | task-class heuristics (labels → branch verbs → diff size) |
| `attribute.py` | orchestrates join+cost; per-ticket rollups + coverage |
| `forecast.py` | per-class distributions, roadmap forecast, anomaly flags |
| `recommend.py` | per-class routing recs, scored net of rework |
| `report.py` / `cli.py` | the 30-second VP-readable report |

## Deferred to later phases (deliberately not in P0)

Cursor / Claude-Code ingestion adapters; SSO/SCIM-fed identity graph; a learned
task-class model; budget-vs-actual burndown per epic; proxy-based **enforcement**
of routing policy; multi-provider rate tables. The integration surface
(N providers × M planners) is the treadmill *and* the moat — it's prioritized by
what design partners actually use, not built generically up front.

## Open product decisions (need founder input)

1. **Billing model** — flat SaaS (lead with zero-install read-only attribution)
   vs. %-of-savings like ModelPilot (needs the enforcement proxy to be core).
2. **First real integration pair** — confirm Anthropic + GitHub Issues is where
   the earliest design partners live, or repoint P0 (e.g. Cursor + Jira).
