# Spec — Procurement-mix optimization (seat plans vs. API credits)

**Status:** shipped (engine `outlay/planmix.py`, console card on `/app/outlay/commitment`,
CLI `--planmix`, MCP `procurement_mix`, `people` rollup in `to_dict`).
**Posture:** advisory, read-only, metadata-only — same as `commitment.py`.

## 1. The problem

Companies buy AI compute two ways:

1. **Flat-fee seat/subscription plans** (Claude Team/Enterprise seats, Claude Max for
   Claude Code, ChatGPT Enterprise, Cursor, Copilot) — a fixed $/seat/month that
   bundles a bounded amount of usage.
2. **API credits / pay-as-you-go** — per-token billing, no floor, no cap.

Compute spend is **wildly uneven across employees**: a few engineers dominate; most
staff (HR, ops, sales) are light. So:

- Buying **seats for everyone** wastes money on light users (paying a flat fee that
  exceeds their usage).
- Buying **API for everyone** pays a per-token **premium** on the heavy users, for whom
  a subscription seat bundles far more value than its fee.

Because engineers will exceed any seat plan's included usage anyway, companies often
default to buying API for everyone — and overpay. There is a cheaper **mix**: seats for
the heavy users, API for the light ones. The only way to compute it is **per-employee
spend**, which Outlay already attributes (and which raw-API buyers cannot see). This is
the fourth procurement mode alongside `commitment.py`'s on-demand / committed-spend /
provisioned throughput.

## 2. The cost model

Normalize everything to **API-equivalent dollars** — what a person's tokens *would* cost
at API list rates (exactly what the attribution pipeline computes). For person *i* with
monthly API-equivalent usage `uᵢ`, and a seat plan *p* with flat fee `f_p` and included
capacity `c_p` (the API-$ a seat covers before usage spills back to API at full rate):

```
cost_on_api(i)     = uᵢ
cost_on_plan(i, p) = f_p + max(0, uᵢ − c_p)      # flat fee + overflow at API rates
```

Two breakevens fall out, per person:

- **Below `f_p`** (light users): the flat fee isn't justified → **API**.
- **Above `f_p`** (heavy users): the seat wins; saving = `min(uᵢ, c_p) − f_p`, growing
  until the seat **saturates** at `c_p`, after which incremental usage overflows to API
  and the saving plateaus at `c_p − f_p`. That plateau is the **premium** a heavy user
  pays on all-API.

## 3. The optimizer (`optimize_mix`)

1. Per person, pick the cheapest mode across the catalog (`_best_mode`).
2. **Prune** any plan whose realized savings across its assignees can't cover its
   overhead — `platform_fee + (min_seats − n_assignees)·fee` (the empty seats an
   enterprise floor forces you to buy). Re-assign its people and repeat until stable.
   This is what stops a 70-seat Enterprise plan being "recommended" for 2 heavy users.
3. Report: per-person assignment, optimal **seat counts** per plan, **status quo**
   (everyone on API — the honest common baseline), **optimized** total (incl. overhead),
   **savings** and rate, a **capacity sensitivity band** (re-solve at ±30% on `c_p`),
   and any **`(unattributed)`** spend (can't be seated → left on API, flagged).

Pure, stdlib-only, back-testable — no I/O, no provider calls.

## 4. Inputs & the fidelity caveat

The optimizer consumes **per-person API-equivalent monthly spend** (`report["people"]`,
window-normalized). We measure the portion of compute that flows through **API usage**;
we do **not** see usage *inside* an existing subscription seat. So:

- Seat **fees and capacities** are configurable estimates (`PlanOption`, flagged
  `illustrative`), seeded with directional defaults the customer replaces with their
  real terms. A subscription's real limit is rate-based, not a clean dollar figure — we
  model it as an API-equivalent capacity and **show sensitivity** rather than pretend
  precision.
- Existing seats can be supplied by the customer so we don't double-count or re-recommend
  a seat they already hold (future input; the engine already reasons in API-$ throughout).

We never claim to see prompts or subscription-internal usage, and every savings figure is
shown with its assumptions — same honest-savings posture as the rest of Outlay.

## 5. Surfaces

- **Console** — a "Seat plans vs. API credits" card on the Commitments page (the
  "cheapest way to pay" destination; no new nav). Headline savings, seats to buy, the
  per-person movers (with saturation notes), the unattributed caveat, sensitivity band,
  illustrative/advisory footer.
- **CLI** — `outlay --planmix`.
- **MCP** — `procurement_mix` tool.
- **JSON** — `to_dict()` emits the `people` rollup that powers all of the above.

## 6. Future work

- Customer-entered existing-seat map + real plan catalog editing in the console.
- Pooled-usage plans (capacity shared across seats) and volume/tier seat discounts.
- Tie the headline saving into the Opportunities/savings surface and the negotiation
  pack export.
- A "what changed" pacing view as the mix recommendation shifts month to month.
