# Personas & use cases — what ModelPilot optimizes (and what it protects)

Internal, 2026-06-16. Grounded in the actual router taxonomy (`taxonomy.py`) + measured
per-category performance on our 147-prompt calibration set (`goldenset_data/`, CALIBRATION
v0.3). Use this to (a) communicate fit with confidence, (b) tell a customer *which employees /
workflows* benefit (not "everyone"), (c) test ourselves per use case, and (d) prioritize
expansion. Caveat: numbers below are on a synthetic calibration set — the real figure is
measured per customer via the control arm.

## How cost optimization works here (the core idea)
We **route the routable, and protect the rest.** Each request is classified into a task type;
"routine" types route down to the cheapest good-enough model (savings), while genuinely hard
types **stay on the top model** (no savings, but no quality risk). Across every category we hold
**0% false-downgrades** — the conservative default is the feature, not a bug. So:
- **Where we cut cost:** high-volume *routine* work.
- **Where we deliberately DON'T cut cost:** hard reasoning/coding/creative — we keep it on the
  top model and *say so*. That honesty is what lets a quality-paranoid buyer trust us.

## Use-case fitness map (measured, gate 0.60, baseline = Opus)

### 🟢 STRONG — real savings, proven safe (route to Haiku)
| Use case (task type) | What it is | Routed | False-dg |
|---|---|---|---|
| Short Q&A / factual lookup | "what is X", definitions, lookups | 100% | 0% |
| Extraction | pull fields/entities → JSON/table (docs, forms, records) | 89% | 0% |
| Rewrite / reformat | fix grammar, reformat, plain-English, convert | 91% | 0% |
| Translation | language translation, short–medium | 87% | 0% |
| Classification | label / intent / sentiment / triage / tagging | 85% | 0% |
| Summarization (short) | summarize a doc / thread / note | 75% | 0% |
| Simple code / SQL | one function, snippet, regex, single query | 100% routed* | 0% |
*codegen_simple routes fully and safely; "exact-tier" accuracy is lower only because some labels were Sonnet — still 0 false-downgrades.

### 🟡 MODERATE — partial savings (route to Sonnet, context-sensitive)
| Use case | Notes | Routed | False-dg |
|---|---|---|---|
| Summarization (long/dense) | long or operational/legal/clinical content | 66% | 0% |
| Customer-facing drafting | audience-constrained → floored to Sonnet | (routes to Sonnet) | 0% |
| Conversation / advice | general chat, brainstorming, generic advice | 40% | 0% |

### 🔴 PROTECTED — we keep these on the top model (≈0 savings, quality safe)
| Use case | Why it stays | Routed |
|---|---|---|
| Complex coding (multi-file, refactor, architecture) | quality-critical, model-sensitive | 0% |
| Debugging / root-cause | non-obvious reasoning | 0% |
| Math / quantitative reasoning | multi-step correctness | 0% |
| Agentic / tool-using multi-step | error compounds across steps | 0% |
| Open-ended analysis / strategy / judgment | subjective, high-stakes | 0% |
| Creative long-form (essays, marketing, stories) | quality/voice-sensitive (Sonnet floor) | 0% |
*(These are calibrated conservative on purpose — CALIBRATION says don't lower open-ended floors until human-labeled. They cost the same as before; we just don't break them.)*

## Employee personas — who actually benefits
Map a customer's headcount to the buckets. The honest message: **"the high-volume routine work
of these roles gets cheaper; your senior/complex work stays on the top model, untouched."**

| Persona / workflow | Their routine tasks (routable) | Fit |
|---|---|---|
| **Customer support / CX** (+support-AI products) | triage/intent classification, ticket/thread summaries, draft replies, FAQ Q&A, translation | 🟢 **Best fit** — highest-volume routable persona |
| **Operations / back-office / data entry** | document & form extraction, routing/tagging classification | 🟢 Strong |
| **Document/knowledge workers** (paralegals, claims, intake, clinical abstraction, compliance ops) | contract/clause extraction, record summaries, doc classification | 🟢 Strong (the regulated bulk) |
| **Sales / marketing ops** | first-draft emails/copy, lead/data enrichment & extraction, summaries, translation | 🟢–🟡 Strong on routine; long creative is protected |
| **Data / BI analysts** | simple SQL, data extraction, factual Q&A | 🟢 on routine; deep open-ended analysis 🔴 protected |
| **Software engineers** | snippets, regex, single queries, boilerplate | 🟢 on simple; complex/refactor/debug/agentic 🔴 protected |
| **Researchers / strategists / senior analysts** | — | 🔴 mostly protected — we keep quality, rarely cut cost |
| **Writers / content leads** | short rewrites/reformats 🟢; long-form 🔴 | mixed |

### Which of your employees can use it (the "not everyone" line)
**Yes, big savings:** anyone whose work is high-volume + routine — support reps, ops/back-office,
document processors, intake/claims teams, sales/marketing drafting, junior data/eng tasks.
**Protected, not cut:** senior engineers on hard problems, quant/research, strategists, creative
writers — their hardest work stays on the top model (we don't risk it, and we don't bill savings
we didn't make). *"Everyone's routine requests get cheaper; the hard reasoning stays premium."*

## Test plan (per persona / use case — run every release)
The per-category evaluator IS the per-persona test. Mechanism:
```
python -m modelpilot.goldenset.evaluate --labels modelpilot/goldenset_data/labels.jsonl
# + the per-category breakdown script (in this doc's commit) → routed% / correct% / false-dg% per category
```
Targets:
- **Hard gate (all categories): false-downgrade = 0%** at gate ≥0.6 (CI-enforced).
- **🟢 categories:** coverage ≥ ~75% (the savings categories must keep capturing).
- **🔴 categories:** stay protected (≈0% routed) until a **human-labeled** slice proves a cheaper tier is safe (`scripts/build_label_worksheet.py`).
- Grow the per-category n (esp. for any persona we're selling into) so the number is credible for that buyer's traffic shape.

## Product-expansion backlog (to support target customers' use cases)
Driven by the prospect list (`PROSPECTS.md`) — add coverage where target buyers' volume lives:
- **Support/CX & voice** (Leaping AI, Decagon, Sendbird, Gorgias): per-turn routing for live
  voice/chat; transcription-summary; intent-routing depth. (Already strong; deepen + add voice.)
- **Code review / agents** (CodeRabbit, Greptile, Augment, Warp, Factory): route agent *sub-steps*
  (plan/read/lint) down while keeping final codegen on top; review-comment generation.
- **Document/regulated** (Robin AI, Elation, Carta, Inscribe, Eve): structured-output-heavy
  extraction, long-context clinical/legal summarization, clause classification — plus the
  caching lever (long reusable prompts) which these workloads hit hard.
- **Multilingual** extraction/classification for global support.
- **Lower the open-ended floors** (analysis/creative) **only after** a human-labeled slice — the
  biggest locked-up savings, but only safe to unlock with non-AI-graded evidence.

## Honest caveats
- Numbers are on a 147-prompt synthetic set; per-customer truth comes from the control arm.
- "Routes well" ≠ "uses Claude" for a given prospect — verify the prospect's actual task mix
  (the estimator's traffic-profile input is the proxy) before promising a number.
- The 🔴 protected categories are where we make ~no money — that's correct, and it's the basis of
  the trust pitch. Don't oversell savings on reasoning-heavy buyers.
