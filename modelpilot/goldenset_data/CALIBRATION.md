# Golden-set calibration v0 — 2026-06-10

69 prompts (seed corpus) × Haiku 4.5 / Sonnet 4.6 / Opus 4.8, judged by
position-debiased Opus pairwise judge + programmatic grading where `expected`
exists. Labels: **54 haiku / 5 sonnet / 10 opus**.

## Threshold sweep (heuristic router v0, baseline = opus)

| gate | coverage | accuracy | false-downgrade | missed |
|---|---|---|---|---|
| ≤0.50 | 81.2% | 60.9% | 7.2% | 31.9% |
| **0.60–0.80** | **49.3%** | **62.3%** | **1.4%** | **36.2%** |
| 0.90 | 0.0% | 14.5% | 0.0% | 85.5% |

**Calibrated gate: 0.60** (lowest meeting the ≤2% false-downgrade target).
0.60–0.80 are behaviorally identical on this corpus (no router confidence
values fall in that band), so the shipped default of **0.80 stays** — same
measured safety/coverage here, more conservative on unseen traffic.

## Per-category at the calibrated gate

| category | n | correct | missed | false-dg |
|---|---|---|---|---|
| extraction | 8 | 8 | 0 | 0 |
| short_qa | 6 | 6 | 0 | 0 |
| translation | 5 | 5 | 0 | 0 |
| classification | 8 | 6 | 2 | 0 |
| codegen_complex | 4 | 4 | 0 | 0 |
| agentic | 3 | 3 | 0 | 0 |
| rewrite_format | 5 | 4 | 1 | 0 |
| summarization_short | 4 | 2 | 1 | 1 |
| summarization_long | 3 | 2 | 1 | 0 |
| debugging | 4 | 2 | 2 | 0 |
| conversation | 3 | 1 | 2 | 0 |
| codegen_simple | 5 | 0 | 5 | 0 |
| math_logic | 5 | 0 | 5 | 0 |
| analysis_strategy | 3 | 0 | 3 | 0 |
| creative_longform | 3 | 0 | 3 | 0 |

## Findings

1. **The router's wheelhouse is near-perfect.** Extraction, short QA,
   translation, classification: 25/27 exact, zero false downgrades. These are
   also the highest-volume enterprise categories.
2. **The single false downgrade** (seed-027): incident summary for a status
   page, routed haiku, label sonnet. Summarization confidence should drop
   when the source text is operational/incident content — a feature for
   router v1, not a floor change.
3. **All the missed savings are confidence starvation, not wrong floors.**
   codegen_simple (conf 0.55) and math/strategy/creative (conservative
   defaults) never clear the gate, so they ride on opus. The labels say haiku
   was fine — but see the caveat below before acting on that.
4. **Do NOT lower the open-ended floors yet.** math_logic / analysis_strategy
   / creative_longform labeling rests on an LLM judge grading open-ended work
   with n=3–5 per category — the exact place judge leniency is most likely
   and the human-calibration set (ROUTER_TUNING_PLAN.md §3) doesn't exist
   yet. Corpus v0 also skews easy: 78% haiku labels is not what real
   enterprise traffic looks like.

## Next iteration (in order of value)

1. Replace/augment the corpus with real shadow-traffic prompts from the
   gateway pilot (consented), re-stratify, target 300–1000 prompts.
2. Human-label a calibration slice for the open-ended categories; measure
   judge–human agreement before trusting open-ended haiku labels.
3. k=3 worst-case judging on ambiguous items (single-sample noise).
4. Router v1: train on accumulated labels; add content-difficulty features
   (the seed-027 lesson) so confidence reflects content, not just verbs.
