# Outlay — demo runbook (software / AI-native ICP)

The talk-track for the live product demo to the eng-consumption ICP. Pairs with the outbound
playbook (`docs/outbound-playbook.md`) and the leave-behind (`docs/software-icp-leave-behind.pdf`)
to make a complete sales kit: **outbound → demo → leave-behind**.

**Demo thesis:** don't tour features. Run *one* narrative — "AI spend is a black box → here's the
box opened → here's the budget under control → here's how to pay less" — and let two moments land:
(1) **a dollar mapped to a ticket**, and (2) **a forecast back-tested on their own work**. Everything
else is supporting cast. Target 20–25 minutes + discussion.

---

## 0. Before the call (5 min setup)
- Load the **enterprise sample** (`python -m outlay.fixtures.gen_demo`) — ~$79k/quarter across 8
  teams, with the $79k-real-vs-$406k-naive callout. A believable bill makes the numbers land.
- Have **two programs** seeded so Governance shows real pacing (one on-track, one off).
- Hide demo chrome (sample banners, onboarding cards) if screen-sharing.
- Open tabs in narrative order: **Overview → Spend → Accuracy → Governance → Commitments**.
- Re-confirm the prospect's stack from discovery (providers, tracker) so you can say "this is where
  *your* Jira/Anthropic data would land."

---

## 1. Frame (1 min) — name the pain, set the rule
> "I'll keep this to ~20 minutes. The goal isn't a feature tour — it's to show you the one question
> your provider bills can't answer, then answer it. If it's not a real gap for you, I'll tell you."

Anchor on *their* number from discovery: *"You mentioned ~$X/mo across Anthropic and OpenAI with no
clean per-team split — that's exactly what this opens up."*

---

## 2. Overview (2 min) — the black box, quantified
- Show the consolidated spend with the **real-vs-naive callout** ($79k vs $406k).
- Talking point: *"First thing — we cost it right. Cache-aware, reconciled to the invoice. Most tools
  over-count cached tokens 5–10×; if the starting number's wrong, everything downstream is."*
- Don't linger — this establishes credibility, then move to the aha.

## 3. Spend → attribution (5 min) — **THE aha #1**
- Drill from total → team → **work type → a single ticket** with its dollar cost and a **fidelity
  tier** on it.
- The line to say slowly: *"This is the thing no dashboard does. Your provider bill stops at the
  account. We go token → ticket → engineer → feature. Here's what shipping this feature cost."*
- Hit **fidelity**: *"Every dollar carries how confident the join is — call, branch, session, team.
  We'll never hand you a confident per-ticket number that's actually a guess. Finance trusts
  'team-level ±15%'; they never forgive a precise wrong number."*
- **Pause here.** Let them react. This is the moment the demo is for.

## 4. Accuracy → forecast back-test (4 min) — **THE aha #2 (the trust unlock)**
- Show the **leave-one-out back-test**: forecast vs actual on *completed* work, with the measured error.
- The line: *"Anyone can draw a trend line. We forecast your backlog and then prove the error on your
  own delivered work — leave-one-out. So next quarter's number has an error bar, not a finger in the
  air. This is measured on your data in the pilot, not a benchmark we're asserting."*
- Honesty beat: *"Allocating the past is exact; forecasting the future is a range — and we tell you
  exactly how good it is."* (Mirrors the /accuracy page — credibility, not bravado.)

## 5. Governance → programs (4 min) — from report to system of record
- Show a **program budget** with real-time pacing, the **projected-breach date**, and the
  **earned-value on-/off-track** rating.
- The line: *"Now it's not a report you read — it's a budget you act on. Cap a body of work across
  teams, and we flag the breach *weeks before the invoice*, with a date. Here's one on track, here's
  one that's going to blow its estimate."*
- Mention read-only posture in passing: *"All of this is read-only and metadata-only — nothing sits
  in your request path, prompts and keys never leave your box. Nothing for security to clear."*

## 6. Commitments (3 min) — how to pay less (the expansion hook)
- Show the **Commitments** page: spend profile + the committed-spend scenarios with **forfeit risk**,
  the **provisioned** directional read, and **Export negotiation pack**.
- The line: *"Once we know your steady run-rate, we size whether a committed-spend discount beats
  on-demand — and quantify the forfeit risk so you don't over-commit. Export it and take it to your
  vendor. This is usually 15–30% nobody's claimed."*
- Note the opportunities card: *"And we flag caching/batch candidates — advisory, you implement."*

## 7. Close to a pilot (2 min) — the only real ask
> "The honest way to prove all of this is your own data. A pilot is **read-only, metadata-only**, ~2
> weeks, and you walk away with: your attribution-coverage %, a forecast back-test error on your
> completed work, and one program budget with a projected-breach date. If the gap isn't real, you'll
> see that too. Who else needs to be in the room — and can we connect a read-only tracker token this
> week?"

Leave the one-pager (`software-icp-leave-behind.pdf`). Send the recap same day.

---

## Objection handling (the common five)
- **"We already have a cost dashboard (Vantage/CloudZero)."** → *"Keep it for cloud and team
  rollups. We're the layer deeper on the AI line — ticket/feature attribution and a forecast you can
  defend. Teams run both."* (See battlecards §1.)
- **"Our gateway (LiteLLM/Portkey) already caps budgets."** → *"In-path caps are great for
  enforcement. They can't attribute to a feature, forecast the backlog, or size a commitment — and
  many teams can't put a gateway in the path for compliance. We complement it."* (Battlecards §2.)
- **"Is this accurate?"** → Show the back-test again. *"That's the whole point — we measure it on your
  data instead of claiming a number."*
- **"Security review will take forever."** → *"Metadata-only, BYOK, read-only — no prompts, outputs,
  or keys leave your environment. That removes most of the review scope. Here's the Trust Center."*
- **"We could build this ourselves."** → *"You can build a v1 dashboard. The cost is the upkeep — the
  spend→work join across changing providers, the forecast back-test, the governance workflow. We
  maintain that so your engineers ship product."* (Battlecards §4.)

## Demo hygiene
- **Two ahas, max.** Attribution-to-a-ticket and the forecast back-test. If you only land those two,
  it was a good demo.
- **Don't feature-dump.** Skip Estimate/Connect/Settings unless asked — offer them as "happy to go
  deeper after."
- **Use their numbers** wherever the UI allows; "your stack here" beats a generic sample.
- **Stay honest.** Every accuracy/savings claim is "measured on your data in the pilot," never
  asserted. That honesty *is* the differentiation — don't undercut it by overclaiming live.
