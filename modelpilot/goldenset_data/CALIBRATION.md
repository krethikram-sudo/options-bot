# Golden-set calibration

## v0.2 ICP corpus expansion (2026-06-16) — own-data cold-start

Added **30 synthetic, ICP-representative prompts** (healthcare / legal / financial
services), all fully fabricated — **no real PII/PHI** — spanning the routable bulk
(extraction, classification, summarization, translation, rewrite, simple SQL, short
QA) *and* genuinely-hard reasoning (clinical differential, legal argument/negotiation,
option-pricing derivations, investment memos). This is the **no-collection cold-start
prior**: a richer, ICP-shaped corpus we *own*, so new customers in these verticals get
a credible calibration without us ever collecting customer data (see
`FLEET_LEARNING.md` → Decision).

Corpus: **69 → 99 prompts**; labels **75 haiku / 7 sonnet / 17 opus** (less skewed than
v0's 78% haiku). Measured against the same heuristic router (baseline = opus):

| gate | coverage | accuracy | false-dg | missed |
|---|---|---|---|---|
| ≤0.50 | 80.8% | 76.8% | 5.1% | 18.2% |
| **0.60–0.70** | **62.6%** | **77.8%** | **0.0%** | 22.2% |
| 0.80 (shipped) | 57.6% | 74.7% | **0.0%** | 25.3% |

**Zero false downgrades at every gate ≥0.60 holds on the expanded corpus.** Coverage
(56.5%→62.6%) and accuracy (68.1%→77.8%) both rose: the ICP bulk is highly routable and
the router classified all 30 additions correctly (0 false-down, 0 missed) — the hard
reasoning prompts stayed on opus via complex-work signals / low-confidence fallback, the
mechanical ones routed to haiku. Caveat: still synthetic + LLM-judge-grade labels; the
real per-customer number comes from the holdout RCT. Next: keep growing toward 300–1000,
add a human-labeled slice for open-ended categories.

---

# Golden-set calibration — v0 (2026-06-10) + router v0.1 retune (2026-06-12)

## v0.1 retune: content-difficulty features (measured against the same labels)

The labels showed the seed-027 false downgrade was an **audience constraint**
(status-page rewrite), not the content domain — the postmortem and legal
summaries of the same material were haiku-fine. Implemented accordingly:
audience constraints floor summarization/rewrite at sonnet; dense
operational/legal content only reduces confidence (below the 0.8 autopilot
gate). Also fixed a float bug where accumulated penalties (0.85−0.05=0.7999…)
missed the gate by epsilon.

| gate | coverage | accuracy | false-dg | missed | (v0 false-dg) |
|---|---|---|---|---|---|
| 0.60–0.70 | 49.3% | **63.8%** | **0.0%** | 36.2% | 1.4% |
| 0.80 (shipped) | 46.4% | 60.9% | **0.0%** | 39.1% | 1.4% |

**Zero false downgrades at every gate ≥0.60**, accuracy up, coverage intact
at the calibrated gate. Caveats unchanged: n=69 seed prompts; judge-labeled;
seed-012's opus label is likely a programmatic-grading artifact ("38k" vs
"38,000" mismatch) — fix the grader normalization in the next round.

---

# v0 baseline — 2026-06-10

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
