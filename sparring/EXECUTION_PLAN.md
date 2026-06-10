# Execution Plan

Principle: the demo exists to power discovery, not the other way around. No durable
engineering until Experiment A passes and 3 design partners are signed.

## Phase 0 — Throwaway demo (week 1, parallel with interview scheduling)

A single-file prototype is enough to run Experiment A: a CLI or bare-bones web page that
runs the debate state machine against the Claude API with 2 hand-written scenarios, dumps
transcripts to files. No accounts, no DB, no dashboard. Judge pass is a script.

Deliverables:
- [x] Debate orchestrator prototype (state machine + 2 scenarios + fairness contract) — `demo/orchestrator.py`
- [x] Judge-pass script with rubric v0 — `demo/judge.py`, `demo/rubric.yaml`
- [ ] 3 internal dogfood sessions (founder + 2 friendly PMs) to fix obvious failure modes

## Phase 1 — Discovery (weeks 1–4)

Run DISCOVERY_PLAN.md in full. Engineering serves the experiments:
- [ ] 12–16 known-cohort sessions executed and blind-scored (Experiment A)
- [ ] 15–20 customer interviews; pilot ask made in every buyer conversation (Experiment B)
- [ ] Employment-law consults done; bias-audit cost/scope known
- [ ] **Decision gate** (see DISCOVERY_PLAN.md) — go / iterate / kill

## Phase 2 — MVP build (weeks 5–10, only after gate passes)

Build MVP_SPEC.md for shadow-mode design partners:
- [ ] Web app: invite links, consent flow, candidate session UI (streaming text debate)
- [ ] Orchestrator productionized: 6 PM scenario packs in versioned YAML
- [ ] Judge pipeline with citation-required scoring; rubric anchors calibrated from
      Experiment A transcripts
- [ ] Reviewer dashboard: annotated transcript, key-moments reel, rubric scores, PDF export
- [ ] Audit log, data retention config, unscored-practice mode

## Phase 3 — Shadow-mode pilots (weeks 8–16, overlapping)

3+ design partners run it alongside real Staff/Sr PM reqs:
- [ ] Every piloted candidate also goes through the normal process — we record their
      panel outcome and (longitudinally) hire success → the validity dataset begins
- [ ] Weekly partner debriefs; candidate-experience NPS tracked per session
- [ ] Pricing discovery: anchor against Karat-style per-interview pricing vs. per-req SaaS
- [ ] Exit criteria for the phase: at least one partner asks to move from shadow mode to
      using it in-process, and candidate experience holds ≥ neutral

## Phase 4 — First paid (post-week 16, sketch only)

Convert shadow partners to paid; bias audit commissioned before anyone uses scores
in-process in regulated jurisdictions; Greenhouse integration; scenario library to ~20;
decide on the consumer-prep mirror as PLG funnel.

## Open questions (carried, not blocking)

1. **Funnel placement:** replace the take-home (earlier, higher volume, lower trust bar)
   vs. augment the onsite (later, lower volume, higher stakes)? Discovery interviews decide.
2. **Name:** "Sparring" is a codename. Naming matters unusually much here — it has to make
   the adversarial format sound rigorous, not hostile.
3. **Who scores, long-term:** is the durable business the assessment (we score) or the
   infrastructure (their interviewers review our transcripts)? Pilots will reveal where
   customers place trust.
4. **Solo-founder shape:** the founder can author scenarios and run discovery natively;
   the build phase likely needs one strong full-stack engineer or 6 weeks of focused
   founder build time.
