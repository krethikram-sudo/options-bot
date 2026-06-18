# Outlay — roadmap-anchored AI spend governance (Phase 0)

**Outlay is the platform and the primary value proposition:** *"budget and
govern AI compute against the work you actually plan — and are you on track."* It
joins LLM/coding-agent spend to the **work-breakdown units a team already plans
around** — Jira/Linear/GitHub tickets → epics → sprints → roadmap — rather than
to infrastructure tags (API keys, spans, model names) the way every existing
gateway / observability / FinOps tool does. That join is the moat: the incumbent
market lives at the infra layer and structurally can't see the planning system.

**ModelPilot's per-request routing is an optimization *service within*
Outlay, not a separate product.** Outlay owns the full loop — attribution
→ forecast → per-task-class policy → shadow/graduation — and *drives* ModelPilot
as the downstream actuator that executes an approved downgrade on live traffic.
The gateway integration in this package is exactly that: Outlay decides
*which classes* may run cheaper and *when they've earned it*; ModelPilot is the
engine that carries it out. (Pricing/packaging of the two is a later decision.)

## Why this is differentiated (competitive landscape)

The market has four crowded categories, and **none attribute spend to a unit of
planned work or forecast against the roadmap**:

| Category | Examples | Attributes spend to… | Forecasts roadmap? |
|---|---|---|---|
| AI gateways / routers | Bifrost, LiteLLM, Portkey, ClawRouters, Azure Model Router | virtual key, team | no |
| LLM observability | Langfuse, LangSmith, Braintrust, Helicone, Datadog | span, agent-run, user, feature | no |
| FinOps-for-AI | Finout, Vantage, CloudZero, TrueFoundry, OpenLM | model, team, product, customer | no (reactive alerts) |
| Native vendor admin | Cursor Organizations, Anthropic/OpenAI consoles | seat, team (own tool only) | no |

Outlay's three unowned moves: **(1)** the planning-system join
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
  (`outlay.shadow:make_observer`) that logs, on real traffic, what each
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

## Attribution paths (in priority order)

Real-data validation (`VALIDATION.md`) showed passive branch inference can't be
the foundation — it returns 0% in detached-HEAD/remote sessions and varies
0–100% by team hygiene. So attribution resolves the ticket from the most
reliable signal available (`tag.py` → `resolve_ticket`):

1. **Explicit tag** — the launcher/wrapper/CI/proxy declares the ticket
   (`SCOPEPILOT_TICKET`, `tagged()`, or `--` arg). `call` fidelity. *Primary.*
2. **Git branch** — parsed to a key when it isn't `HEAD`. `branch` fidelity.
3. **CI PR-branch env** — `GITHUB_HEAD_REF` recovers the real branch in
   detached-HEAD CI/web runs (the failure mode that scored us 0%).
4. **Commit-message trailer** — `Ticket: PROJ-123` / `Closes #123`.
5. **Jira/Linear join** — for teams whose tracker isn't GitHub Issues.

The branch/PR signals are the zero-config bonus that delights disciplined teams
(60–90% coverage in the audit); explicit tagging is what makes it reliable for
everyone else.

## Ingestion sources & fidelity ceiling

Different sources can reach different join fidelity — surfaced honestly so a
number is never trusted beyond what produced it:

| Source | Carries git branch? | Fidelity ceiling | Role |
|---|---|---|---|
| Claude Code transcripts (`gitBranch`) | yes | `branch` (ticket-level) | primary join |
| Outlay proxy metadata (tagged) | yes | `call` (ticket-level) | primary join |
| Anthropic Admin API (aggregated) | no | `team` (key→user→team) | invoice reconciliation |
| Cursor Admin API (per-user) | no | `team` (user→team) | per-engineer rollup |

Live pulls via clients in `outlay.ingest`, all behind a `urllib` transport
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
   dependency on Outlay and can never alter or block a request.
2. Outlay registers `outlay.shadow:make_observer`. On each request the
   gateway hands it a small payload (decision + token usage + the work
   branch/ticket from `x-modelpilot-work-*` headers); the observer resolves the
   task-class and appends a delta to the shadow log: *what this request cost on
   the model it ran, vs. what the candidate would have cost.*
3. `graduation_report()` aggregates the log; once a class has enough live
   counterfactuals it's `ready_for_canary` — the **cost** gate.
4. `canary.py` is the **quality** gate: it runs the candidate model on a sample
   of the class's real prompts and judges non-inferiority against the incumbent
   (`run_fn`/`judge_fn` injected — in production these are ModelPilot's
   `compare.api_run_fn` / `api_judge_fn`, i.e. the routing product executing the
   test the governance product ordered). `ready_classes()` is the **two-gate**:
   a class graduates to ENFORCE only when it is *both* cost-ready (shadow) *and*
   quality-passed (canary). **Cost evidence accrues automatically; quality is
   measured, never assumed.**

```
export MODELPILOT_REQUEST_OBSERVER=outlay.shadow:make_observer
export SCOPEPILOT_POLICY=policy.json SCOPEPILOT_ISSUES=issues.json
export SCOPEPILOT_PLANNER=github SCOPEPILOT_SHADOW_LOG=shadow.jsonl
```

## Run it

```bash
python -m outlay.cli                 # demo report over bundled fixtures
python -m outlay.cli --window-days 9 # project observed spend to a monthly figure
python -m outlay.cli --usage usage.json --issues issues.json   # real exports
python -m outlay.cli --calibrate     # append a measured forecast-accuracy backtest
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
  over a *class* is stable and useful. Each open item gets a p10..p90 band
  around its class mean, and the roadmap total carries a **variance-pooled**
  interval — independent per-item over/under-shoots partially cancel, so the
  realistic band is tighter than naively summing per-item p90s, while staying
  nested inside that fully-correlated `[Σp10, Σp90]` worst case.
- **Size conditioning is opt-in and earns its place.** Within a class, cost
  often scales with size (`est_points` at plan time, or diff size retrospectively).
  `size.py` fits a per-class cost-per-unit ratio and the forecast uses it for any
  item carrying that signal — a tighter estimate than the flat class mean. But we
  don't assert it helps: the backtest runs an apples-to-apples leave-one-out of
  size-conditioned vs class-mean on the *same* tickets and reports the error
  reduction, so the model is used only where the data shows it works. On the
  bundled fixtures it cuts bugfix median error 346%→116%; items with no size
  signal fall back to the class mean.
- **The forecast's accuracy is measured, not asserted.** `backtest.py` runs a
  leave-one-out cross-validation over realized spend — predict each closed
  ticket from the *others* in its class, compare to actual — and reports MdAPE,
  MAPE, signed bias, and how often the p90 band held. `--calibrate` appends it
  to the report. The number is honest by construction: thin classes are skipped
  (counted, not guessed), and the demo fixtures deliberately score poorly
  because six synthetic tickets are not a calibrated distribution. A real
  accuracy figure comes from a design partner's own history.
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
| `join.py` | branch→ticket join + identity graph + fidelity tiers |
| `tag.py` | **explicit task-tagging** — the primary, reliable attribution path |
| `classify.py` | task-class heuristics (labels → branch verbs → diff size) |
| `attribute.py` | orchestrates join+cost; per-ticket rollups + coverage |
| `forecast.py` | per-class distributions, roadmap forecast, anomaly flags |
| `backtest.py` | **calibration** — leave-one-out backtest of forecast accuracy + size-vs-class proof |
| `size.py` | **size conditioning** — per-class cost-per-point/diff ratio model |
| `recommend.py` | per-class routing recs, scored net of rework |
| `policy.py` | **enforcement** — gated routing policy for the ModelPilot proxy |
| `shadow.py` | **live loop** — gateway observer, shadow ledger, cost graduation |
| `canary.py` | **quality gate** — non-inferiority trial + two-gate graduation |
| `budget.py` | **burndown** — actual vs scope-based budget, pace-projected |
| `dogfood.py` | `python -m outlay.dogfood` — one-command real-data run |
| `audit.py` | `python -m outlay.audit` — join-convention rate across public repos |
| `report.py` / `cli.py` | the VP report + `--emit-policy` / `--budgets` |

## Budgets & guardrails (the original value prop)

*Build budgets from the scope of work, then hold spend within guardrails.*
`budget.py` tracks actual spend against a per-scope budget (epic / team / sprint
/ total) and **projects the end-of-period total at the current burn rate**, so a
lead sees a scope trending over *before* it blows through — not after. Guardrails
are pace-based (`ok` / `warn` / `over`), never hard mid-period caps that just stop
work. Budgets can be set by hand (`--budgets budgets.json`) or derived straight
from the roadmap forecast (`budget_from_forecast`).

```
[WARN ] June AI compute (whole team)   spent $13.01/$45.00 (29%) at 29% of period
                                        projected end: $45.06 (over by $0.06)
[OVER ] Epic: Q3 stability             spent $6.43/$5.00 (129%) → projected $22.27
[OK   ] Team: platform                 spent $4.39/$20.00 (22%) → $15.61 headroom
```

## Dogfood it (real-data validation — run on your machine)

The cheapest test of the whole bet is the real ticket-coverage %. Run it against
your own Claude Code transcripts (which carry `gitBranch`) and your repo's live
issues — no exports, no proxy:

```python
from outlay.ingest import GitHubIssuesClient, parse_claude_code_dir
from outlay.cli import _FIXTURES  # or build the report parts directly
# 1. pull real issues:   GitHubIssuesClient(token=...).pull("you", "your-repo")
# 2. parse real usage:   parse_claude_code_dir("~/.claude/projects")
# 3. attribute + report  (see outlay.cli.run)
```

or via the CLI once you've exported issues to JSON:

```bash
GITHUB_TOKEN=… python -m outlay.cli \
    --planner github --issues my_issues.json \
    --claude-code ~/.claude/projects --window-days 30
```

The headline number to watch is **ticket coverage** — if real branches resolve
to real tickets, the product works; if they don't, that's the thing to fix first.

## Deferred to later phases (deliberately not in P0)

SSO/SCIM-fed identity graph; a learned task-class model; budget-vs-actual
burndown per epic; non-Anthropic provider rate tables (GPT/Gemini). The
integration surface (N providers × M planners) is the treadmill *and* the moat —
prioritized by what design partners actually use.

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
6. **Product framing — Outlay is the platform / primary value prop;**
   ModelPilot's routing is an embedded optimization *service within* it (the
   actuator Outlay drives). Pricing/packaging of the two is a later decision.
7. **Graduation loop — shipped, two-gate.** `canary.py` adds the quality gate;
   a class enforces only when cost-ready (shadow) *and* quality-passed (canary).
8. **Planner pullers — all three live** (GitHub, Jira, Linear API clients).
9. **Budget burndown — shipped.** `budget.py` tracks actual vs scope-based budget
   with pace projection (`--budgets`) — the founding value prop, end-to-end.
10. **CI — Outlay has its own gate.** `.github/workflows/outlay-ci.yml`
    runs the test suite on every change to `outlay/` (the primary product).
11. **Attribution rebalanced (evidence-backed).** Real-data validation showed
    passive branch inference is unreliable as a foundation; `tag.py` makes
    **explicit task-tagging the primary path**, branch/PR the zero-config
    fallback. See `VALIDATION.md` for the full trail.
