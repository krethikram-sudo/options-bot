# Thesis

## Problem

Hiring for judgment-heavy roles (PM, strategy, leadership, senior eng) is broken in a
specific way: the interview formats companies use don't surface how a candidate *reasons*.

- **Panel interviews** reward polish and rehearsed frameworks. Every PM candidate has
  memorized CIRCLES and a "tell me about a conflict" story.
- **Take-homes** now measure how well someone uses an LLM, not how they think. Post-2023,
  every written artifact is AI-assisted; the artifact is no longer the signal.
- **Behavioral interviews** measure storytelling about past reasoning, not reasoning itself.
- **Live case studies** are the best existing format, but they're expensive (senior
  interviewer time), inconsistent (interviewer skill varies wildly), and unrecorded
  (the debrief is a game of telephone).

The thing hiring managers actually want to know — *can this person take a position, defend
it with evidence, absorb a counterargument, and update honestly?* — is exactly the thing
none of these formats reliably measures.

## Insight

A frontier LLM is a near-ideal sparring partner for exactly this evaluation:

1. **It can argue any side, calibrated to any difficulty,** consistently across hundreds of
   candidates. No human interviewer is this consistent.
2. **Debate is AI-cheat-resistant by construction.** You can't outsource a live, adversarial,
   evolving conversation to another LLM in real time without it being obvious. The format
   that AI broke (take-homes), AI also fixes.
3. **The transcript is the artifact.** Every claim, concession, pivot, and dodge is recorded
   and can be annotated, scored, and replayed for the hiring panel. Debriefs go from
   "vibes" to evidence.
4. **The candidate experience can actually be good.** Strong candidates *enjoy* a real
   intellectual fight far more than a fifth round of "walk me through your resume."

## What it is

A B2B assessment platform. A company configures a role (e.g., Staff PM), picks or generates
scenarios, and sends candidates a link. The candidate has a 30–45 minute structured debate
with Claude: a case scenario where Claude takes and defends positions against them, plus
behavioral scenarios where Claude probes and challenges their accounts. The hiring team gets
back a scored, annotated transcript with a highlights reel of the moments that matter.

## Who buys it

- **Buyer:** Head of Talent / recruiting ops at 200–5,000 person tech companies; hiring
  managers for PM/strategy/leadership roles as champions.
- **Initial wedge:** Staff/Senior PM hiring. It's the role where (a) the pain is sharpest,
  (b) the founder has native expertise to build credible scenarios and rubrics, and
  (c) there is no incumbent skills-test (HackerRank has nothing for PMs).
- **Expansion:** strategy/biz-ops, consulting, senior engineering design debates, internal
  promotion calibration, and interview *prep* (the consumer mirror of the same product —
  cheaper to serve, worse economics, but a possible PLG top-of-funnel).

## Why now

- Take-home assessments collapsed as a signal in the last ~2 years; companies know it and
  haven't replaced them with anything.
- Models are now good enough to sustain a genuinely adversarial, multi-turn debate and to
  judge one against a rubric with citations into the transcript.
- Interview-intelligence tools (BrightHire, Metaview) normalized recording and AI analysis
  of interviews — the category taboo is already broken.

## Competition

| Player | What they do | Why we're different |
|---|---|---|
| HackerRank, CodeSignal | Coding assessments | No judgment-role coverage at all |
| Karat | Outsourced human technical interviews | Human-powered, expensive, eng-only |
| Sapia.ai, HireVue | AI chat/video screening | Screening Q&A, not adversarial debate; measures communication, not reasoning under challenge |
| Mercor, micro1 | AI interviews for talent marketplaces | Marketplace-captive; assessment isn't the product |
| BrightHire, Metaview | Record/analyze human interviews | They instrument the old format; we replace it |

The defensible asset over time is not the debate agent (models commoditize) — it's the
**scenario library, the scoring rubrics, and the validity dataset** linking debate
performance to hire outcomes.

## Top risks (ranked)

1. **Validity risk — does debate skill predict job performance?** Eloquent arguers who are
   bad operators exist; great operators who debate poorly exist. If the signal doesn't
   discriminate, the product is theater. → This is the #1 thing discovery must test
   (see DISCOVERY_PLAN.md, Experiment A).
2. **Legal/compliance risk — this is an employment selection tool.** AI-driven assessments
   are regulated and getting more so: NYC Local Law 144 requires annual bias audits of
   automated employment decision tools; Illinois and Colorado have AI hiring laws; the EU
   AI Act classifies hiring AI as high-risk; EEOC disparate-impact doctrine applies
   regardless. Debate-style assessment may also disadvantage non-native speakers and some
   communication styles — a real adverse-impact exposure, not just paperwork. We need an
   employment-law review and a bias-audit plan *before* the first paid customer, and the
   product posture should be "decision support with human review," never auto-reject.
3. **Buyer trust risk.** Recruiting leaders are conservative; "an AI argued with your
   candidate and scored them" is a scary sentence. Mitigation: position as a *structured
   interview with a perfectly consistent interviewer*, full transcript transparency, human
   reviewer in the loop.
4. **Candidate acceptance risk.** Senior candidates may refuse an AI interview as
   disrespectful. Mitigation: make it earlier-funnel (replaces the take-home, not the
   final panel), and make the experience genuinely engaging.
5. **Platform risk.** Anthropic/OpenAI could ship adjacent capability. Mitigation: the moat
   is rubrics + scenario library + outcomes data + enterprise trust, not the model call.

## What would kill this (pre-mortem, one line each)

- The validity experiment shows scores don't separate known-strong from known-weak operators.
- Hiring managers love the demo but legal/HR blocks every deal → sell to scale-ups without
  mature HR-legal first, with compliance artifacts ready.
- Candidates rate the experience as degrading → invest in tone, difficulty calibration, and
  a "you'll debate an AI, here's why" candidate-facing explainer from day one.
