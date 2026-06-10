# Discovery Plan

Goal: kill or confirm the two assumptions that everything else depends on, in ~4 weeks,
before building anything beyond a throwaway demo.

## Riskiest assumptions, in order

| # | Assumption | If false... | How we test |
|---|---|---|---|
| A | Debate performance discriminates between known-strong and known-weak operators | Product is theater | Experiment A (validity) |
| B | Hiring managers will trust and pay for an AI-debate assessment | No buyer | Interviews + Experiment B (pilot intent) |
| C | Senior candidates will engage rather than refuse | Top-of-funnel breaks | Candidate-side sessions in Experiment A |
| D | Claude can sustain a fair, calibrated adversarial debate for 30–45 min | Core UX fails | Falls out of A/C sessions |
| E | Compliance is navigable for scale-up customers | Sales cycle dies in legal | 2–3 employment-law consults + LL144 audit scoping |

## Experiment A — known-cohort validity test (the make-or-break)

**Design:** Recruit 12–16 people whose operating quality we already know with confidence —
half "known strong" (Staff+ PMs we'd hire on sight, referred by trusted operators), half
"known weaker but credentialed" (people with strong resumes whose work we or referrers know
to be mediocre). Everyone does the same 35-minute Claude debate session: one PM case
scenario, one behavioral scenario. Sessions are scored blind by (1) the Claude judge pass
and (2) two human Staff+ PM reviewers reading transcripts without names.

**Pass condition:** Blind rubric scores (human and model) correctly separate the cohorts
with at most 2 misclassifications out of 16, AND human reviewers say the transcript told
them something a resume + panel would not have.

**Fail condition:** Scores cluster or invert; reviewers say transcripts read as "who is
better at talking." If it fails, iterate scenario design twice; if it still fails, this
idea dies here, cheaply.

Also harvested from these sessions: candidate-experience ratings (assumption C), debate
agent failure modes (assumption D), and the first 50 annotated "moments" to seed the
highlights-reel feature.

## Customer interviews (assumption B)

15–20 interviews, three segments:

1. **Hiring managers for Sr/Staff PM roles** (8–10) — the champion. Probe: how do you
   assess reasoning today, where do panel debriefs go wrong, what did you do when
   take-homes died, would you trust this transcript, what score would change a decision?
2. **Heads of Talent / recruiting ops at 200–5,000 person companies** (5–6) — the buyer.
   Probe: assessment budget today (what do they pay Karat/CodeSignal-class tools?),
   procurement path, who has to say yes (legal? DEI? works council?), what compliance
   artifact unblocks them.
3. **Recently-hired Staff PMs** (3–4) — the candidate. Probe: would you have done this?
   At what funnel stage does it feel respectful vs. insulting?

**Interview discipline (Mom Test rules):** ask about past behavior and current spend, not
"would you buy." The only forward-looking ask is the Experiment B commitment below.

## Experiment B — pilot intent

End every buyer/champion interview with a concrete ask: *"We're running paid design
partnerships — $X for unlimited use on one open req this quarter, you get the transcripts
and scores alongside your normal process (shadow mode, no decisions made on it)."*

**Pass condition:** 3+ signed shadow-mode design partners (paid or with a signed LOI)
out of ~15 conversations.

Shadow mode matters: running alongside real hiring decisions builds the validity dataset
(did our score predict who they hired and who succeeded?) without triggering the full
compliance burden of an automated employment decision tool.

## Compliance track (assumption E, parallel)

- 2–3 consults with employment-law counsel: what does shadow-mode vs. decision-mode
  trigger under NYC LL144, Illinois, Colorado, EU AI Act?
- Scope what a bias audit costs and requires, so it's a line item, not a surprise.
- Draft the candidate-consent and data-retention posture now; it shapes architecture.

## Decision gate (end of week 4)

| Outcome | Action |
|---|---|
| A passes + 3 design partners | Build the MVP (see MVP_SPEC.md), raise or self-fund deliberately |
| A passes, <3 partners | Signal is real, packaging is wrong — iterate positioning/funnel stage, extend 3 weeks |
| A fails after 2 iterations | Kill, or pivot to the consumer prep mirror (validity bar is much lower for prep) |
