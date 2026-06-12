# ModelPilot — GTM execution plan (internal)

Focus decision (2026-06-12): **SF-style startups / small enterprise**, per
ICP in PILOT_OUTREACH.md. Consumers = free extension as top-of-funnel only.

**Goal: 3 completed design-partner pilots in 6 weeks → 1–2 paid by week 10.**

## Funnel math (plan to these numbers, adjust from reality)

```
20 qualified targets → 10 conversations → 5 shadow installs
                     → 3 completed 2-week pilots → 1–2 paid conversions
```

If a stage converts at half the planned rate, the fix is at THAT stage
(more targets / better demo / easier install / stronger report), not
generalized effort.

## Phase 0 — launch checklist (this week, ~2 days)

- [ ] Publish the beta repo (`./scripts/publish_modelpilot.sh ~/modelpilot-beta
      git@github.com:YOUR_ORG/modelpilot.git`), fix YOUR_ORG placeholders,
      enable Pages on it or keep using the live gated page
- [ ] Run `modelpilot compare --judge` ONCE live with your key on the seed
      corpus → keep the HTML as the demo's proof exhibit
- [ ] Flip your own gateway to autopilot for a week of dogfood
      (`MODELPILOT_MODE=autopilot ./scripts/install_modelpilot_gateway.sh`)
- [ ] Rehearse DEMO_SCRIPT.md twice, including the chat let-them-drive opener
- [ ] Manually check notdiamond.ai/pricing + withmartian.com/pricing
      (COMPETITIVE.md TODO)
- [ ] Build the 20-target list (below) in pilot_tracker.csv

## Building the 20-target list

Qualify against ICP: $5K+/mo Claude spend (proxy signals: "powered by
Claude" showcase, Claude API in job posts, support/doc/assistant product),
eng-led, warm path preferred.

Starting hypotheses to verify, by segment (companies BUILDING on Claude-class
APIs — verify provider + spend signals before outreach; this list is a
brainstorm, not research):
- **Support AI:** Decagon, Sierra, Forethought, Ada, Pylon, Plain
- **Legal/doc AI:** Harvey, EvenUp, Eve, Reducto, Tennr, Extend
- **Embedded assistants:** vertical SaaS w/ AI copilots (health ops, fintech
  back-office, real-estate ops — browse recent YC batches)
- **Second wave (note, don't lead):** agent platforms, AI consultancies/
  agencies running client workloads (one logo = many workloads)

Warm-path inventory FIRST: list every founder/eng leader you can reach in ≤2
intros before any cold outreach. Target mix: ≥8 warm, ≤12 cold.

## Phase 1 — outreach (weeks 1–2)

- Cadence: 5 touches/day, 4 days/week (1 day reserved for product/pilot ops).
  Warm intros before cold email; cold = PILOT_OUTREACH template + the gated
  landing page link/password.
- The ask is always the same and always small: **20-min demo → 2-week shadow
  mode on one service, zero behavior change, one base_url line.**
- Every conversation, even a "no": ask the two discovery questions —
  (1) what's your monthly Anthropic spend and which workload dominates?
  (2) what would make you trust an auto-router? Log verbatim in tracker.

## Phase 2 — pilot operations (weeks 2–6)

Per pilot:
1. **Onboarding call (30 min):** install together (shadow), agree success
   criteria from PILOT_OUTREACH (≥20% potential savings, ≤25ms p95, zero
   incidents), agree the quality margin BEFORE data exists.
2. **Day 3 check:** traffic flowing? dashboard sane? fix fast — install
   friction is the #1 pilot killer.
3. **Week 1:** send their shadow report + run `compare --judge` on 20 of
   their prompts (with consent) — the mid-pilot wow moment.
4. **Week 2 close:** would-have-saved report + proposal: flip to advise on
   one route, or autopilot with the calibrated gate. Their captured corpus
   (opt-in) feeds their per-tenant calibration — the lock-in begins here.
5. Max 3 concurrent pilots (solo-founder support capacity).

## Phase 3 — conversion (weeks 6–10)

- **Beta pricing posture:** simple flat founder-pricing beats savings-share
  for the first deals — e.g. **$500/mo (<$25K spend) or $1,500/mo (above)**,
  3-month commitment, "design-partner price locked for 12 months."
  Savings-share (15–20% of verified) is the v2 model once RCT numbers are
  routine; don't make deal #1 a negotiation about measurement.
- Trade: case study + logo rights for a discount. The first public
  "X verified 31% savings, zero quality regressions" is worth more than the
  revenue delta.

## Weekly operating rhythm (solo founder)

| | |
|---|---|
| Mon–Thu AM | Outreach + pilot check-ins (the business) |
| Thu PM–Fri | Product: ONLY pilot-blocking fixes + corpus/calibration work |
| Friday EOD | Update tracker; funnel review against plan numbers |

Product discipline: no new features unless a pilot is blocked on it. The
backlog (replay job, policy engine, trained router) gets prioritized by what
pilots demand, not by what's interesting.

## Metrics & adjust/kill criteria

- **Shadow reports show <15% potential savings on real traffic** → the
  workload thesis is off; re-target segments before re-building product.
- **Installs stall on security questions** → write the self-host hardening
  doc / start SOC2-lite; that's the demanded feature.
- **Demos don't convert to installs (<1 in 3)** → demo problem, rehearse +
  lead harder with `compare`.
- **No warm path produces a conversation in 2 weeks** → expand to cold +
  communities; consider a public launch (HN Show) of the offline demo.

## Tracker

`pilot_tracker.csv` — update every Friday. Stages:
`target → contacted → call → shadow → pilot → report → paid / lost`.
