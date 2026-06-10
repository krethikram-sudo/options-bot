# MVP Spec

Scope: one role (Staff/Senior PM), text-based debate, shadow-mode pilots. Everything else
is deferred (see EXECUTION_PLAN.md).

## Session flow (candidate side)

1. **Invite link** → candidate-facing explainer: what this is, why a debate, what's
   recorded, consent. (Tone here is a product feature — see Risk 4 in THESIS.md.)
2. **Warm-up (3 min):** low-stakes exchange so the candidate acclimates to the format
   before anything is scored.
3. **Case debate (20 min):** a PM scenario with a genuine trade-off (e.g., "kill or keep a
   beloved low-revenue product," "ship fast with known debt vs. slip the quarter").
   Claude opens by taking a defensible position. The candidate must take a side and argue
   it. Claude escalates through staged pressure levels: counter-evidence → steelmanned
   opposing case → attack on the candidate's weakest premise → a late fact that should
   change the answer (tests updating vs. entrenchment).
4. **Behavioral debate (12 min):** candidate gives a real experience ("a time you made a
   call with incomplete data"); Claude probes it like a skeptical board member — pushes on
   inconsistencies, asks what they'd concede in hindsight, challenges the decision they
   defended.
5. **Close (2 min):** candidate gets one open rebuttal — "what did the AI get wrong about
   your argument?" (often the highest-signal moment), then a candidate-experience survey.

Timeboxing is enforced by the orchestrator, not the model.

## Debate agent design

- **Not a chatbot with a persona — a state machine that uses Claude per state.** States:
  warm-up, position-taking, pressure levels 1–3, fact-injection, rebuttal, close. Each
  state has its own system prompt, objectives, and exit criteria. The orchestrator (code)
  decides state transitions from elapsed time + a lightweight per-turn assessment; the
  model never controls session structure.
- **Calibrated difficulty:** pressure escalates only when the candidate handles the current
  level; a struggling candidate gets a fair fight at level 1, not a pile-on. The goal is
  to find the ceiling, not to win.
- **Fairness constraints in the agent contract:** no gish-galloping (one challenge at a
  time), no moving goalposts without flagging it, concede when the candidate lands a
  point (concessions are signal too), plain language, no rhetorical tricks the rubric
  doesn't credit candidates for countering.
- **Scenario packs as data, not code:** YAML — scenario brief, Claude's opening position,
  evidence bank for each side, the level-3 "late fact," rubric weights. MVP ships with 6
  PM scenarios; this library is the long-term moat, so the format gets versioned from day one.

## Scoring

Two-layer, with humans in the loop by design (also the compliance posture):

1. **Judge pass (Claude, separate context from the debate agent):** scores the transcript
   against the rubric, and must cite specific turns for every score. No citation, no score.
2. **Human review:** the hiring team sees scores *with* the annotated transcript and a
   "key moments" reel (position taken, best argument, concession handled well/poorly,
   response to the late fact). The product output is decision support, never a verdict.

**Rubric (v1, 6 dimensions, 1–5 each, anchored with examples):**

| Dimension | What it measures |
|---|---|
| Position quality | Took a clear, defensible position; named its costs honestly |
| Argument structure | Claims supported by reasons/evidence, not assertion or framework recital |
| Pressure response | Engaged the strongest counterargument rather than dodging or repeating |
| Updating | Changed their mind when the late fact warranted it — and *didn't* when it didn't |
| Intellectual honesty | Conceded real points; flagged their own uncertainty; no bluffing |
| Synthesis | Final position integrated the debate rather than restating the opening |

Inter-rater work in the validity experiment (DISCOVERY_PLAN.md, Experiment A) calibrates
both the anchors and the judge prompt before any customer sees a score.

## Architecture (MVP)

```
Candidate browser ──► Web app (Next.js) ──► Orchestrator (session state machine)
                                                 │
                                ┌────────────────┼──────────────────┐
                                ▼                ▼                  ▼
                          Claude API        Postgres           Judge pipeline
                       (debate states)   (sessions, turns,   (async post-session:
                                          scenarios, scores)  judge pass → annotations)
                                                 ▲
                              Reviewer dashboard ┘ (transcript, moments, scores, export)
```

- **Model:** Claude API (latest Sonnet-class model for debate turns; Opus-class for the
  judge pass where quality per token matters most). Streaming responses; per-turn latency
  budget < 3s to keep debate tempo.
- **Text-first, voice later.** Voice is more natural for debate but adds STT/TTS latency,
  accent bias (a compliance problem, not just a UX one), and cost. Text also produces the
  cleanest transcript artifact. Revisit after pilots.
- **Compliance-shaped from day one:** candidate consent flow, configurable data retention,
  full audit log of every prompt/response, scores never shown without transcript access,
  and a kill switch to run any session in "unscored practice" mode.
- **Anti-cheat (MVP-level only):** paste-detection, focus-loss telemetry, and timing
  analysis — flagged to reviewers, never auto-failing anyone. The deeper defense is the
  format itself: real-time adversarial dialogue is hard to proxy.

## Out of scope for MVP

Voice; roles beyond PM; ATS integrations (Greenhouse/Lever come at first paid expansion);
customer-authored scenarios (we author all six); auto-decisions of any kind; consumer prep
product; SOC 2 (start the controls checklist, defer the audit).
