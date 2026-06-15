# Self-optimize tier: how much more does tuning on your own data save? (internal)

Drafted 2026-06-16. The question customers ask: *"Is Self-optimize ($99/mo + 15% of
savings) worth it over Pay-as-you-go (20%, no fee)?"* This is the honest evaluation we
use to answer it — and the source for the customer-facing decision tools (console
billing panel `_tier_decision_panel`, site pricing copy).

## The two value drivers (both real, keep them separate)
1. **Rate cut (guaranteed):** 20% → 15% of savings, for a flat $99/mo. Pure arithmetic,
   no modeling. On its own it only wins for high savers (see break-even).
2. **Tuning uplift (estimated):** routing is tuned on the customer's *own* traffic, so it
   safely captures savings the global Pay-as-you-go floors leave on the table.

## Why tuning uplift exists (the mechanism)
PAYG uses **global** calibrated floors + a conservative confidence gate (0.60) that must be
safe across *every* customer's traffic. So it leaves headroom unused — on the golden set,
**31.9% of traffic is routable-down but the global gate stays on the big model** ("missed").

A single customer's traffic within a category is far more **homogeneous** than the global
average. Self-optimize runs `floorlearn`: for each category it tests the next-cheaper tier on
*their* prompts, judges non-inferiority, and **lowers the floor only where it holds up on their
data** (admin-approved). That recovers much of the missed headroom **without** raising
false-downgrades, because each lowering is empirically validated on the customer, not on a
global gate. (Option A: only traffic *metadata* — category, token counts, outcomes — is used;
prompt content never leaves the box. IP stays server-side; the gate is enforced at
`/api/policy`, which serves learned floors only to Self-optimize/Managed.)

## Measured uplift (illustrative, golden set — NOT a per-customer promise)
`python -m modelpilot.goldenset.evaluate` + a per-category-floor simulation:

| Plan | Coverage | Blended bill cut (Opus baseline) |
|---|---|---|
| Pay-as-you-go (global gate 0.60) | 56.5% | 43.5% |
| Self-optimize (realistic, ~70% of gap captured) | ~77% | ~59% |
| Self-optimize (ceiling / perfect per-category floors) | 85.5% | 65.5% |

**Incremental savings uplift vs PAYG: ~35% realistic, up to ~51% ceiling** (≈ 15–22 more
percentage points of the bill). We quote a conservative **15–35%** range in customer materials.

Caveats (state them — do not let marketing round them off):
- 69-prompt synthetic golden set; it's a regression harness, not a customer study.
- The "~70% of gap" capture is an assumption; real capture depends on how homogeneous and
  how routable the customer's traffic is.
- Uplift is **larger** for customers with lots of repetitive, currently-over-served bulk work
  (our regulated ICP: document classification, extraction, intake/record summarization) and
  **smaller** for customers whose traffic is mostly hard reasoning or already cost-tuned.
- The real number is **measured per customer** via the held-out control arm once they're on
  the tier — never asserted after the fact.

## The economics (what a customer should compute)
Let `S` = monthly savings under PAYG, `u` = relative tuning uplift, fee = $99/mo.
- Keep under PAYG: `0.80·S`
- Keep under Self-optimize: `0.85·S·(1+u) − 99`
- Self-optimize wins when: `S > 99 / (0.85·(1+u) − 0.80)`

Break-even monthly savings by uplift:

| Uplift `u` | Break-even monthly savings | Notes |
|---|---|---|
| 0% (rate cut only) | ~$1,980 | pure volume discount; only high savers benefit |
| 15% | ~$760 | |
| 25% (midpoint) | ~$377 | the rule-of-thumb we show |
| 35% | ~$285 | |

So: with a believable 15–35% uplift, Self-optimize pays for itself once monthly savings clear
roughly **$285–$760** — a bar most of our ICP ($5k+/mo Claude spend → typically >$1k/mo
savings) clears comfortably. Below ~$300/mo savings, keep them on Pay-as-you-go.

## Decision guidance (what we tell customers)
- **Start on Pay-as-you-go** while ramping: no fee, no commitment, proves the savings.
- **Move to Self-optimize when** (a) monthly savings are roughly >$300–$500, AND (b) you have
  repetitive task categories (extraction/classification/summarization/intake) where tuning has
  room to safely lower floors. The console billing page shows this from your *actual* savings.
- **Stay on Pay-as-you-go if** your spend is low or your traffic is mostly hard, one-off
  reasoning (little routable headroom for tuning to recover).

Honesty rule: never sell the uplift as guaranteed. The guaranteed part is the rate cut; the
uplift is measured on their own traffic with the control arm, and we show the rate-cut-only
"worst case" right next to the upside.
