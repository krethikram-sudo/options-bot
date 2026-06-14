# Maven starter packs

Per-segment starter policies so a new customer gets a good fit on **day one** —
before their own `learn-rules` / `learn-floors` have accumulated traffic.

A pack maps your domain's phrasing to the right category (and a conservative
floor), and — for regulated segments — ships a compliance `profile`. These
encode the domain-judgment phrasings that are intentionally **not** in the
global router (legal redlines, compliance scoring, clinical extraction), so they
only ever apply when you opt into your segment's pack.

## Use

Point one env var at your pack — the gateway reads its rules, gates, floors, and
profile together:

```bash
MODELPILOT_POLICY=packs/doc-extraction.json modelpilot gateway --mode guidance
```

(Start in guidance, watch the dashboard, then switch to autopilot — same flow as
always.) You can also hand-edit a pack, or merge several by combining their
`category_rules`.

## Available packs

| Pack | For | Posture |
|---|---|---|
| `doc-extraction.json` | invoice/contract/data extraction, classification | Aggressive — Haiku for bulk extract/classify (the savings jackpot) |
| `support.json` | customer support / CX automation | Aggressive on triage/QA/replies; RAG answers floored to Sonnet |
| `coding.json` | coding agents / dev tools | Haiku for simple codegen; refactors/debugging stay strong (global router) |
| `legal.json` | legal AI | Conservative — Opus→Sonnet only, never Haiku; Sonnet min-model floor |
| `healthcare.json` | clinical / insurance | Regulated — Sonnet floor + conservative gate; review your compliance duties |

## Safety

Packs are **opt-in** and never bypass the guardrails: the cache-aware economics
veto, the structured-output/tool floor (schema-enforced calls never drop below
Sonnet), the randomized holdout, and escalation netting all still apply. Treat a
pack as a strong starting prior — then let `learn-floors` confirm (or pull back)
each category on *your own* traffic.
