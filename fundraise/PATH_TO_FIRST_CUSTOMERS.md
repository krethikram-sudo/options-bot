# Outlay — path to first customers (do this BEFORE the pre-seed)

The strategic call: **don't raise on a deck — raise on proof.** A pre-seed with
2–3 design partners and one "this found money we couldn't see" quote outraises a
perfect deck with zero validation, and at a better price. This is the plan to
manufacture that proof in ~8 weeks.

The whole product was built to retire one assumption: **can we attribute a real
team's AI spend to their real work, end-to-end?** Public data de-risked the
*mechanism* (60–90% joinable where GitHub is the tracker). The only thing left is
doing it on a live team. That's what these weeks are for.

---

## Definition of "raise-ready" (the bar that ends this phase)

Stop prepping the round and start running it when **all** of these are true:

1. **3+ design partners live** (read-only data connected, report delivered).
2. **≥1 quantified, referenceable finding** — e.g. "Outlay showed $`[X]`k/quarter
   on one epic we'd mis-budgeted" or "flagged a downgrade worth $`[Y]`k/mo" — from
   a named person willing to be a reference.
3. **≥60% ticket coverage demonstrated end-to-end** on at least one real team
   (the make-or-break metric, now proven, not modeled).
4. **≥1 signal of willingness to pay** — a verbal "we'd pay for this," a paid
   conversion, or a signed LOI.

Hit those four and the traction slide writes itself; until then, more deck polish
has diminishing returns.

---

## The offer that makes pilots easy to say yes to

The wedge is a **read-only, ~2-week, zero-instrumentation audit** (already
written up in `OUTLAY_PILOT_OUTREACH.md`):

- They connect **one tracker (GitHub Issues / Jira / Linear) + their AI usage
  (Anthropic admin API, Cursor admin export, Claude Code transcripts)** — all
  read-only.
- We return: **spend mapped to tickets/epics/teams + a coverage number + a quarter
  forecast + anomaly flags + a savings estimate** — prompts never leave their env.
- Free for design partners. Their cost is ~30 min of setup + candid feedback.

This is the lowest-friction version of the product *and* the exact thing that
produces the proof number. The audit **is** the pilot.

---

## The funnel (and the metric at each stage)

```
List ─→ Outreach ─→ Call ─→ Connected ─→ Coverage% ─→ "Aha" finding ─→ Reference / LOI
        (reply%)   (book%)  (setup done) (≥60%?)      (≥1 real $)     (raise-ready)
```

Target conversion to get to 3 live partners: ~**40–60 well-targeted contacts → ~8–12
calls → ~4–6 connects → 3 that complete**. So the top of funnel is **~50 quality
contacts**, not a mass blast.

---

## 8-week sprint

**Week 0 — set up to sell (2–3 days)**
- [ ] Finalize the **target list**: 50 contacts in the ICP — eng orgs ~20–150,
      on GitHub Issues with PR/ticket hygiene, Claude Code/Cursor-heavy, with a
      VP/Dir Eng or FinOps person who feels the pain. (Warm network first.)
- [ ] Stand up a **simple CRM** (a sheet): company · contact · ICP-fit · source ·
      stage · coverage% · outcome. The `coverage%` column is the one that matters.
- [ ] Dry-run the **onboarding** end-to-end on a friendly target or your own
      best-discipline repo so setup is genuinely 30 min, not a debugging session.
- [ ] Lock the **3-minute demo** (dogfood/`--json` → coverage + calibration
      accuracy + savings).

**Weeks 1–2 — outreach + first calls**
- [ ] Send **warm intros first** (one intro beats 50 cold emails), then cold via
      the templates in `OUTLAY_PILOT_OUTREACH.md`. ~15–20 contacts/week.
- [ ] Goal: **5–8 discovery calls booked.** On each, confirm fit, agree the
      success bar up front, pick tracker + usage source.

**Weeks 2–4 — connect + deliver the audit**
- [ ] Get **3–4 partners connected** (read-only). Aim for first coverage number
      within days of connection.
- [ ] Deliver the **audit readout** live — walk their real numbers. Hunt for the
      one **"aha" finding** (over-pace epic, a real downgrade, a mis-budgeted team).

**Weeks 4–6 — turn audits into evidence**
- [ ] For each partner: capture the **coverage %**, the **finding ($)**, and a
      **quote** you can use. Ask explicitly: *"would you be a reference?"*
- [ ] Push at least one toward **willingness-to-pay**: "if we turned on guardrails
      + the optimization engine next quarter, is this a budget line for you?" Get a
      verbal, an LOI, or a paid pilot.

**Weeks 6–8 — package the proof + line up the raise**
- [ ] Update the **deck traction slide** (#10) with real coverage/finding/quote.
- [ ] Build the remaining fundraise artifacts (one-pager, model, investor list).
- [ ] Begin **warm investor intros** only once the bar above is met.

---

## Product / ops gaps that block conversion (close these as they bite)

These are the things most likely to stall a pilot — fix reactively, in priority:
- [ ] **Onboarding friction.** The read-only connect (admin API keys, tracker
      token, transcript path) must be genuinely 30 min with a clear runbook. If a
      pilot stalls here, everything downstream stalls.
- [ ] **Jira/Linear coverage.** Most enterprise ICP isn't on GitHub Issues —
      confirm the Jira/Linear planner join + explicit tagging actually fire on a
      real instance (don't rely on GitHub-issue parsing for them).
- [ ] **The readout artifact.** The `--json`/report needs to render as something a
      VP reads in 30 seconds (a clean PDF/one-screen summary), not a terminal dump.
      This is the deliverable that becomes your reference quote.
- [ ] **Coverage rescue.** If a partner's branches aren't ticket-named and they're
      not on GitHub Issues, the explicit task-tag path must be a 5-minute add — or
      coverage looks worse than the product really is.

> Rule: don't build ahead of a pilot. Let a real partner's blocker pull the next
> bit of work. That keeps you building what converts, not what's interesting.

---

## Pricing for the first cohort
- **Design partners: free**, in exchange for data access, candid feedback, and a
  reference. Explicitly time-boxed (the pilot), so "free forever" isn't the anchor.
- **First paid:** when you convert, anchor to **value, not cost** — a fraction of
  the spend you make visible and reduce (the ~$25k ACV hypothesis from
  `MARKET_SIZING.md`). The pilot's own finding is the price justification.

## Why this sequencing wins
- It **retires the one risk** the whole thesis rests on (end-to-end attribution on
  a real team) with the cheapest possible instrument (a read-only audit).
- It produces the **traction slide** that turns a hard pre-seed into an easy one.
- It generates **real pricing + ICP signal**, so the model and deck stop being
  guesses.
- Worst case, the pilots reveal the product needs work — far better to learn that
  on free design partners than after a priced round.

## This week's three actions (start here)
1. Build the 50-name target list (warm network first).
2. Send the first 10 warm intros / outreach emails.
3. Dry-run onboarding so the first "yes" doesn't die in setup.
