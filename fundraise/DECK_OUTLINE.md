# Outlay — pre-seed deck outline

11 core slides + appendix. Pre-seed bar: make the **wedge obvious**, the **why-now
undeniable**, and show you're a founder who ships. One idea per slide, big type,
few words. Speaker notes are what you *say*; the slide shows less.

`[bracketed]` = insert a real number/asset before sending. Source docs to mine:
`fundraise/NARRATIVE.md`, `outlay/PITCH.md`, `outlay/VALIDATION.md`,
`MARKET_STUDY_2026.md`, `COMPETITIVE.md`, `ICP.md`, `GTM_PLAN.md`.

---

## Slide 1 — Title / one-liner
- **On slide:** `Outlay` wordmark + *"Budget your AI engineering spend by the work
  that drives it."* + your name/contact + outlay-ai.com.
- **Notes:** the one-liner from NARRATIVE.md. 10 seconds. Set the frame: this is
  about *governing AI spend*, the line item every eng org is now staring at.

## Slide 2 — Problem
- **On slide:** *"Every eng org can see their AI bill exploding. None of them can
  say what it's being spent on."* Three bullets: spend keyed by API key/model, not
  work · can't forecast by roadmap · no warning before a team blows budget.
- **Notes:** Make it visceral — the CFO asks "why is this $`[X]`k and climbing?",
  the VP Eng has no breakdown. Spend lives in provider dashboards; nobody can tie
  it to an epic, a team, a sprint.

## Slide 3 — Why now
- **On slide:** 3 forces: (1) coding agents went mainstream → AI is now a top-3
  eng line item; (2) the data to join spend↔work just became available (admin
  APIs + tracker APIs + agent transcripts); (3) FinOps-for-AI is forming and
  unowned.
- **Notes:** This is the slide that makes it a *now* company. Cloud FinOps became
  a multi-$B category when cloud spend got big and ungoverned — AI coding spend is
  at that exact inflection, and it lives where the FinOps suites can't see it.

## Slide 4 — Solution
- **On slide:** the 4-move arc as a simple left→right: **Attribute → Forecast →
  Guard → Optimize.** One line each.
- **Notes:** Attribute every $ to a ticket/epic; forecast the quarter from open
  scope; guardrails that warn *before* overspend; then route spend down with proof.
  "The predictability of a fixed-salary engineer with the leverage of AI."

## Slide 5 — Product / demo (the credibility slide)
- **On slide:** a real screenshot/terminal of the dogfood or `--json` run —
  coverage %, the forecast with its band, the **measured** calibration accuracy,
  and a savings figure. Caption: *"It states its own coverage and refuses to fake
  a number it can't back."*
- **Notes:** This is where a technical VC leans in. Walk the 3-min live demo if
  it's a meeting. The honesty layer (calibration backtest, control-arm savings) is
  a *trust* asset, not a hedge. Built and shipped — not vaporware.

## Slide 6 — Wedge & moat (the "why you win" slide)
- **On slide:** Wedge: *day-one value for GitHub-Issues teams, zero
  instrumentation.* Moat: 3 icons — **planning-system join**, **privacy by
  architecture (metadata-only)**, **proven savings + aligned billing.**
- **Notes:** The join is the IP incumbents can't reach from the infra layer.
  Privacy-by-architecture locks out the one set of players (LLM observability) who
  could otherwise copy attribution — and opens the regulated segment. We earn when
  the bill goes *down*.

## Slide 7 — Market (bottoms-up)
- **On slide:** bottoms-up TAM/SAM/SOM. Frame: `[# AI-heavy eng orgs]` ×
  `[avg annual AI coding spend per org]` × `[take rate]` = `$[SAM]`. SOM = your
  reachable ICP (the high-discipline GitHub-Issues cluster) first.
- **Notes:** Do NOT do top-down "1% of a $X B market." Build it from orgs ×
  spend × take. Anchor to cloud FinOps as the analog category size. *(Numbers TBD
  in the market-sizing artifact — flag as next deliverable.)*

## Slide 8 — Business model
- **On slide:** flat SaaS platform fee **+** a share of *realized* savings;
  expansion to regulated/enterprise premium. One line on why it expands (more
  tools, more teams, chargeback).
- **Notes:** Land on attribution/forecasting (clear SaaS value), expand into the
  savings-share once the optimization engine proves out. Savings-aligned billing
  is the trust unlock; flat SaaS is the predictable base VCs want to see.

## Slide 9 — Competition
- **On slide:** 2x2 or table. Axes: *sees the planning layer* × *acts on spend
  (not just observes)*. Us alone in the corner. Others: FinOps suites (cloud, not
  eng work), LLM observability (ingest prompts; observe, don't act), native
  consoles (per-key totals), gateways/routers (infra; read the prompt).
- **Notes:** Pull straight from `COMPETITIVE.md` / the live `/compare` page. Be
  generous and precise — VCs trust founders who describe competitors fairly.

## Slide 10 — Traction (honest, momentum-framed)
- **On slide:** what's real: product shipped (attribution + forecast + optimization
  engine, ~`[40.7%]` measured savings in a smoke test) · site live · mechanism
  de-risked on real data (6,534 events ingested; 60–90% joinable where GitHub is
  the tracker) · **`[N]` design-partner pilots in progress** `[update before
  sending]`.
- **Notes:** Don't dress up zero pilots as traction. Frame as *velocity +
  de-risked mechanism + the riskiest assumption now being tested with named
  partners.* If you've got even one pilot quote, this becomes your strongest slide
  — prioritize getting it before the raise.

## Slide 11 — Team & the ask
- **On slide:** you (`[1-line bio: what makes you the person to build this]`) +
  build velocity proof (shipped a full platform solo). The ask: **$`[1.0]`M
  pre-seed** → milestones: `[5–8]` design partners → `[2–3]` paying → `$[X]`k ARR
  + `[2]` hires in `[18]` mo.
- **Notes:** Address solo-founder head-on: either the cofounder search or why you
  can carry it now + first hires. End on the specific milestones the money buys —
  that's what they're underwriting.

---

## Appendix slides (hold in back pocket, pull on question)
- **Why it's a company, not a feature** — the rebuttal from NARRATIVE.md.
- **"What if Anthropic/Cursor builds it?"** — incentive misalignment + neutral
  cross-vendor referee + single-tool blindness.
- **The attribution problem in depth** — fidelity tiers, detached-HEAD recovery,
  Jira/Linear join, cache-aware costing. (Mine VALIDATION.md — the honest
  0%→fix story is *compelling*, not a weakness.)
- **Privacy architecture diagram** — metadata-only data flow (reuse the
  /security page graphic).
- **Pricing detail & unit-economics hypothesis.**
- **18-month plan / use of funds.**
- **Roadmap** — attribute → forecast → govern → optimize → chargeback.

## Deck-building notes
- Format: Google Slides or Pitch; 11 slides + appendix; send as PDF.
- Design: lean on the outlay-ai.com design system (Fraunces + Inter, green/amber/
  red budget palette, tabular numerals) so the deck and product feel like one
  brand.
- Two versions: a **send deck** (reads standalone, more text) and a **present
  deck** (sparse, you narrate).
- Replace every `[bracket]` before it leaves your hands. A placeholder in a VC
  deck reads as "not ready."

## Sequenced next artifacts (after this)
1. **Market sizing** (fills Slide 7) — bottoms-up model.
2. **One-pager** (the teaser that gets the meeting).
3. **Financial model + use of funds** (Slides 8/11 detail).
4. **Investor target list** + warm-intro map.
5. **Objection-handling FAQ** (the appendix, expanded).
