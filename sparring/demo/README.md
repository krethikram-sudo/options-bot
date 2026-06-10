# Sparring — Phase 0 demo

Throwaway prototype that exists to run the validity experiment (DISCOVERY_PLAN.md,
Experiment A) and dogfood sessions. No accounts, no DB, no web UI — a terminal debate
and a scoring script. Don't harden this; the MVP (MVP_SPEC.md) replaces it.

## Setup

```bash
cd sparring/demo
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run a debate session (~20-30 min)

```bash
python orchestrator.py scenarios/sunset_beloved_product.yaml --candidate "Jane Doe"
# or
python orchestrator.py scenarios/ship_or_slip.yaml --candidate "Jane Doe"
```

The orchestrator walks a fixed state machine — warmup → position-taking → counter-evidence
→ steelman/weakest-premise → new-information injection → open rebuttal → close — and gives
Claude a per-state directive on top of a stable fairness contract (one challenge at a time,
concede landed points, switch sides if the candidate agrees with it). Type `/quit` to end
early; partial transcripts are still saved and scorable.

Transcripts land in `transcripts/<session>.json` (+ a readable `.md`).

## Automated test run (no typing required)

A second Claude context can play the candidate under a persona. Running both personas on
the same scenario and comparing judge scores is a one-command miniature of the validity
experiment — the judge should clearly separate them:

```bash
python simulate.py scenarios/ship_or_slip.yaml --persona strong --judge
python simulate.py scenarios/ship_or_slip.yaml --persona weak --judge
```

The `weak` persona is deliberately the dangerous profile: eloquent, framework-dropping,
never committing — the candidate that fools panel interviews. If the judge can't score
that persona below the `strong` one, the rubric or scenarios need work before Experiment A.

## Offline smoke tests (no API key)

```bash
python test_demo.py
```

Mocks the model and verifies state-machine sequencing, transcript structure, early-quit
handling, the cacheable system-prompt layout, simulator role-flipping, and the judge's
no-citation-no-score rule.

## Score a transcript

```bash
python judge.py transcripts/<session>.json
```

The judge runs in a separate context from the debate agent, scores the six rubric
dimensions in `rubric.yaml` (1-5, anchored), and must cite candidate turn numbers for every
score — uncited scores are voided. It also extracts the key moments a reviewer should read
first. Output is decision support only; it never produces a hire/no-hire verdict.

## Known limitations (deliberate, Phase 0)

- **Fixed turn budget, no difficulty calibration.** The MVP spec calls for escalating
  pressure only when the candidate handles the current level; here every state gets a
  fixed number of exchanges.
- **Turn-based, not time-boxed.** No wall-clock enforcement.
- **No behavioral scenario yet.** Both scenarios are case debates; the behavioral-probe
  state type is an MVP feature.
- **Rubric anchors are unvalidated.** They get re-anchored against real transcripts after
  Experiment A, with inter-rater checks against human reviewers.
- **Single judge pass.** No ensemble, no human-agreement measurement yet.

## Adding a scenario

Copy one of the YAMLs in `scenarios/` and fill in the same fields: `brief`,
`claude_position`, `evidence_for_position`, `evidence_against_position`, `late_fact`,
`late_fact_guidance`. The late fact should be information that *should* change the shape
of a good answer — the guidance field tells the debate agent what strong vs weak updating
looks like so its follow-up probe is calibrated.
