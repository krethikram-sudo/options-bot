# Outlay — pitch

**Tagline:** *Budget by scope of work, stay within guardrails, and capture the
savings automatically.*

## One-paragraph pitch

Outlay turns AI compute from an unpredictable, runaway line item into
something you can budget and govern like any other engineering cost. Today's
tools meter AI spend by infrastructure — API keys, models, dashboards — but no
one can answer the question leadership actually asks: *"what is this body of
planned work costing us, and are we on track?"* Outlay is the first platform
to attribute every dollar of LLM and coding-agent spend to the **work you already
plan** — the Jira/Linear/GitHub tickets, epics, and roadmap — by resolving the
git branch each AI agent runs on back to its ticket. From that join it forecasts
a quarter's cost from its scope, tracks actuals against budget with pace-based
guardrails that flag a team *before* it blows through, and then safely drives
spend down: it learns per-work-type which cheaper model is provably good enough
(validated in shadow, then a quality canary) and enforces that routing through an
embedded optimization engine. The result is the predictability of a fixed-salary
engineer with the leverage of AI.

## Positioning notes

- **Outlay is the platform and primary value prop.** ModelPilot's
  per-request routing is an optimization *service within* it — the actuator
  Outlay drives, not a separate product.
- **The moat** is the planning-system join (branch/PR → ticket → epic →
  roadmap). Incumbent gateways/observability/FinOps tools live at the infra
  layer and structurally can't see the planning system.
- **The make-or-break metric** is ticket coverage: the fraction of real spend
  that resolves to a real ticket.
