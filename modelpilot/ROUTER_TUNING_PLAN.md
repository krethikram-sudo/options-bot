# ModelPilot — Router Tuning Plan

This is the make-or-break system. The plan below treats routing as a supervised learning
problem with an unusual label, an asymmetric loss, and a permanent online feedback loop.

## 1. Problem statement

For each request `(prompt, context)`, predict the **cheapest model whose output is
non-inferior to the baseline model's output for this request**.

Definitions that keep this honest:

- **Baseline model** = the model the request would have used without us (org default or
  caller-specified).
- **Non-inferior** = a defined quality bar, not "identical." Operationally: a strong judge
  (and humans on a calibration set) cannot find a meaningful defect in the cheap model's output
  that the baseline's output avoids, for *this task's* success criteria.
- The label is therefore a function of the prompt **and** the candidate models' actual
  behavior — which is why labels come from running the models, not from human intuition about
  difficulty.

Why this is genuinely hard, named explicitly:

1. **Difficulty is not surface-visible.** "Summarize this contract" can be Haiku-trivial or
   Opus-hard depending on the contract. Features must include the *content*, not just the
   instruction.
2. **Quality is task-relative.** A one-word classification has a checkable answer; a strategy
   memo doesn't. The quality bar must be defined per task category.
3. **Errors are asymmetric.** A wrong upgrade wastes cents; a wrong downgrade can produce a
   wrong answer a user acts on. The objective must encode this.
4. **Context changes the answer.** Cache state and expected conversation continuation can
   flip the economics entirely (see PRODUCT_DESIGN.md §3).
5. **The ground truth moves.** New models, new prices, model behavior drift. Tuning is a
   process, not a project.

## 2. Phase 0 router (bootstrap, weeks 1–6)

Before any training data exists, ship a **Haiku-4.5-as-router** zero/few-shot classifier:

- A carefully engineered prompt asks Haiku to classify the request into a task taxonomy
  (~15 categories: classification, extraction, factual Q&A, summarization, translation,
  code-gen-simple, code-gen-complex, debugging, math/logic, multi-step agentic, creative
  long-form, analysis/strategy, safety-sensitive, etc.) and rate difficulty signals.
  A deterministic policy table maps (category, difficulty, context features) → model.
- Cost ≈ $0.0003–0.001/request, latency 300–600ms — acceptable for shadow mode (off the hot
  path), too slow/expensive as the permanent hot-path solution.
- Every Phase-0 decision is logged with full features → this *is* the start of the training
  corpus.

Phase 0 exists to (a) power the shadow-mode sales report and (b) generate candidate labels —
not to be right 99% of the time.

## 3. Golden dataset (the core asset)

### Construction

1. **Sample real traffic** (with customer consent in pilots; plus public/synthetic corpora —
   instruction datasets, agent traces, support tickets, code tasks — re-shaped to match
   enterprise traffic mix). Target: 10–20K prompts initially, stratified by task category,
   prompt length, and context depth.
2. **Fan out:** run every prompt on all candidate models (Haiku 4.5, Sonnet 4.6, Opus 4.8;
   Fable 5 where relevant). Use the Batch API — 50% off makes the fan-out affordable, and the
   golden set is exactly the non-latency-sensitive workload batching is for.
3. **Grade:** for each prompt, pairwise-compare each cheaper model's output against the
   baseline model's output.
   - **Judge ensemble:** a strong judge model grades with a per-category rubric
     ("non-inferior / inferior-minor / inferior-major"), position-debiased (swap A/B order,
     require agreement), with self-consistency (k=3 samples, majority).
   - **Verifiable tasks get programmatic grading:** code → run the tests; extraction →
     field-exact-match; classification → label match. Programmatic beats judge wherever
     possible.
   - **Human calibration set:** 500–1,000 items double-labeled by humans. Purpose: measure
     judge–human agreement per category. Categories where the judge disagrees with humans
     >10% get human-labeled at higher rates or excluded from auto-routing until fixed.
4. **Label:** cheapest model graded non-inferior. (If Haiku is non-inferior → label Haiku,
   else try Sonnet, etc.)

### Known biases and their controls

| Bias | Control |
|---|---|
| Judge favors verbose/its-own-style outputs | Pairwise with position swap; rubric scores task success, not style; programmatic grading where possible |
| Judge is itself a Claude model grading Claude | Spot-audit with a second-family judge + the human calibration set |
| Single-sample noise (models are stochastic) | k=2–3 generations per model on ambiguous items; label by worst-case (a model that's non-inferior only sometimes is inferior) |
| Dataset drifts from real traffic | Quarterly re-stratification against live traffic mix; per-customer fine-tuning slices |

## 4. The production router (Phase 1+)

### Architecture: cascade

```
request ──► feature extractor ──► fast model ──► confident? ──► decision
                                        │ no (ambiguous band)
                                        ▼
                              Haiku judge (or: default to baseline)
```

- **Features:** prompt embedding (small local embedding model); scalar features — prompt
  length, code/markup presence, instruction-verb class, conversation turn count, accumulated
  context tokens, cache-prefix size, prior model, customer/route ID, task category from a
  lightweight classifier head, historical conversation-length distribution for this route.
- **Fast model:** gradient-boosted trees or a small MLP over embedding+scalars. Targets:
  <20ms inference, fully local (privacy), explainable feature attributions (the "rationale"
  string in the API response).
- **Ambiguous band:** middle-confidence requests either go to the Haiku judge (Mode 1, where
  latency tolerance is higher) or **default to the baseline model** (Mode 2 hot path — when
  unsure, do nothing). The do-nothing default is the single most important safety property.

### Asymmetric objective

Train and threshold with an explicit cost matrix (numbers are starting points, tuned per
customer risk appetite):

| | Predicted cheaper | Predicted baseline |
|---|---|---|
| **Truth: cheaper is fine** | 0 (win) | small (missed savings) |
| **Truth: cheaper fails** | **10× penalty** (quality incident) | 0 |

Operationally: pick the confidence threshold per category so that the expected
**false-downgrade rate ≤ 1–2%** on the golden set, and accept whatever savings rate that
yields. Report both numbers; let admins move the slider (the policy engine exposes
conservative/balanced/aggressive presets).

### Cache- and continuation-awareness

The classifier predicts *capability* (can the cheap model do it?). A separate **economics
layer** decides whether to act: expected remaining conversation tokens (from per-route
historical distributions) × price delta, minus cache-rewrite penalty. Both must be positive
to recommend a switch. This separation keeps the ML problem clean and the dollar logic
auditable.

## 5. Online learning loop (Phase 2+)

Offline accuracy decays without live feedback. Signals, from strongest to weakest:

| Signal | Interpretation |
|---|---|
| Escalation re-run succeeded where downgrade failed (Mode 2 valve) | Hard negative — gold-quality training example, auto-captured |
| User regenerates / immediately rephrases the same ask | Soft negative |
| User manually overrides recommendation upward (Mode 1) | Soft negative on the recommendation |
| Customer app's own validation failed (webhook we expose) | Hard negative, customer-defined quality |
| Thumbs-down / CSAT sample | Soft negative |
| Request completed, no retry, conversation moved on | Weak positive (abundant; use with care — silence ≠ success) |

Mechanisms:

- **Active learning:** the ambiguous band (where the fast model is least confident) is exactly
  where labels are most valuable. Sample it continuously into the fan-out → judge → golden-set
  pipeline (Batch API, off-peak).
- **Champion/challenger:** retrained router ships behind the current one in shadow; promote
  only when it beats champion on the frozen golden set *and* on live regret.
- **Per-customer calibration:** global model + per-tenant threshold calibration (their traffic
  mix and risk appetite differ). Optionally per-tenant fine-tune for large accounts.
- **Drift tripwires:** weekly automated re-run of a 500-item golden subset; alert on category-
  level non-inferiority shifts (catches silent model-behavior changes and our own regressions).
- **New-model protocol:** when Anthropic ships a model or changes prices, the full golden set
  re-runs against the new lineup before the router may recommend it. Price tables are config;
  the Models API is polled for lineup changes.

## 6. Metrics (what "accurate" means)

**Router quality (offline, golden set):**
- Routing accuracy vs. oracle label, per category
- **False-downgrade rate** (the metric; target ≤1–2% at chosen threshold)
- Coverage: % of traffic where we recommend a change at all

**Business outcome (online):**
- $ saved per 1K requests (RCT-measured, see SAVINGS_DASHBOARD.md)
- **Regret** = missed savings (too-conservative) + incident-weighted quality failures
  (too-aggressive), in dollars — the single number leadership tracks
- Escalation rate (Mode 2), override rate (Mode 1), follow-rate (Mode 1)

**Quality guardrail (online):**
- Routed vs. holdout: regenerate rate, escalation rate, customer-validation failure rate —
  must be statistically indistinguishable (non-inferiority test) for the savings claim to stand

## 7. Timeline and dependencies

| Weeks | Work |
|---|---|
| 1–4 | Task taxonomy + rubrics; Phase-0 Haiku router; logging schema |
| 3–8 | Golden set v1 (10K prompts × all models via Batch API); judge ensemble; human calibration set |
| 7–12 | Fast router v1 trained; threshold tuning to false-downgrade target; shadow A/B vs Phase-0 router |
| 12+ | Online loop: escalation capture, active learning, champion/challenger, drift tripwires |

Budget note: golden set v1 fan-out ≈ 10K prompts × ~4 models × ~3K avg tokens round-trip —
roughly $1–3K at batch prices including judging. Trivial against what's at stake; rerun freely.
