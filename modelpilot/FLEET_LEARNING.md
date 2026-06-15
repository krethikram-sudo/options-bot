# Fleet learning: privacy-safe cross-customer calibration (internal)

Drafted 2026-06-16. The second moat (pairs with ICP.md hardening #4). How we get
**exponentially better at routing for every customer — existing and new — using
cross-customer signal, without ever collecting prompt content.**

## The idea
Two streams of **derived, non-invertible** signal per request (never text):
1. **Request-shape cells** — granular attributes of the session, computed locally.
2. **Tuning outcomes** — what routing change was tried for that shape, and whether it held up.

Aggregate these across all opted-in customers into a **global prior**: *"for a request of
shape S, the cheapest tier that stays non-inferior is T, with confidence C."* Feed that prior
back as the **warm-start floor** for new and under-sampled customers. More customers → denser
cells → sharper priors → better routing for everyone, especially **new customers on day one**.

Why it's a moat no one can copy:
- Prompt-reading routers (OpenRouter/Martian) **can't make the privacy claim** while doing this.
- A pure no-data posture has **no cross-customer outcome graph** to learn from.
- We sit in the only defensible spot: a cross-customer *outcome* graph built entirely from
  non-invertible metadata. (Honest: this is a compounding data advantage with diminishing
  returns per added customer — not literally exponential. The sharp edge is **cold-start**:
  new customers get good routing immediately instead of weeks of conservative ramp.)

## Stream 1 — request-shape cells (no text, ever)
Today telemetry is keyed by `category`. We extend the key to a **coarse bucketed shape**, all
computed locally and structurally non-invertible:

| field | example values | notes |
|---|---|---|
| `category` | classification, extraction, codegen_complex… | existing local label |
| `ctx_bucket` | xs / s / m / l / xl (log-bucketed token count) | bucket, not the count |
| `out_bucket` | s / m / l (requested_max_tokens bucket) | |
| `has_tools` | bool | |
| `has_structured_output` | bool | |
| `has_code` | bool | |
| `turns_bucket` | 1 / 2-3 / 4-8 / 9+ | |
| `lang` | en / es / code / other (label only) | local detector → label, never text |
| `vertical` | healthcare / legal / fintech / general | customer's self-declared segment |

A "cell" = a combination of these. It describes the *shape* of a request precisely while being
impossible to invert to content (it's a handful of buckets and booleans).

## Stream 2 — tuning outcomes per cell
For each cell, what we *learned* by trying a cheaper tier (this already exists per-customer in
`floorlearn` + `proofs` + escalations; we aggregate it):

| field | meaning |
|---|---|
| `tried_tier` | the cheaper tier evaluated for this cell |
| `n_validated` | side-by-side / holdout comparisons made |
| `non_inferior_rate` | share judged non-inferior at `tried_tier` |
| `escalation_rate` | share that had to bump back up |
| `regenerate_rate` | quality-failure signal |

This is the "tuning changes that were made + their result," cell by cell — the exact thing that
transfers across customers.

## The privacy guarantees (this is what makes it safe AND honest)
**"Metadata only" is NOT automatically private** — granularity is the enemy; a high-dimensional
per-request vector could fingerprint. Safety comes from *structure*, not the word "metadata":

1. **Coarse buckets only** — log-bucketed sizes, booleans, labels. No raw counts, no timestamps
   finer than the window, no per-request rows ever leave.
2. **k-anonymity at the cell** — a cell is only shared/used if it aggregates **≥ k requests from
   ≥ m distinct customers** (e.g. k=50, m=5). Sparse cells are suppressed. (We already do this for
   catch-all phrase signals; extend it to every cell.)
3. **Differential privacy (optional, stronger claim)** — add calibrated Laplace noise to cell
   counts/rates under a tracked ε budget, so no aggregate can be attributed to one customer. This
   buys the marketable line: *"we can mathematically bound what the fleet model could reveal about
   you — provably nothing."*
4. **Opt-in + explicit consent** — gated on the existing `telemetry_opt_in` flag; Self-optimize
   makes the value plain ("contribute anonymized outcomes, get the fleet's learning back"). The
   most paranoid no-egress customers **decline and still benefit** from the prior — they just
   don't contribute. The flywheel runs on the opt-in majority.
5. **Published, inspectable schema** — `modelpilot telemetry --preview` already shows exactly what
   would send. We publish the cell schema so a security reviewer can verify non-invertibility
   themselves. The transparency is itself a trust asset for our ICP.
6. **Server refuses non-aggregates** — `ingest/` already 422s any payload with forbidden keys
   (prompt/output/key fields); keep that as defense-in-depth.

**This is a new data use beyond "nothing leaves the box."** It must be opt-in, consented, and
covered in the ToS/DPA as de-identified aggregate telemetry. We never silently repurpose the
ephemeral routing-decision features into a stored cross-customer model.

## The learning mechanism (warm-start without breaking safety)
- The brain builds a **global prior** floor per cell from the fleet aggregate: the cheapest tier
  whose fleet `non_inferior_rate ≥ threshold` at adequate volume.
- For a given customer, the effective floor = **hierarchical blend** of their own validated data
  (strong when they have it) and the fleet prior (carries the cold-start). Bayesian shrinkage:
  trust the prior when the customer is under-sampled, trust their own data as it accumulates.
- **Safety invariant preserved:** the prior only sets a *starting* floor; a customer's own
  holdout/escalation signal can always override it *upward*. We never route a customer below what
  their own data supports for long — the prior just removes the cold-start penalty. The
  0%-false-downgrade discipline (control arm + non-inferiority) still governs locally.

## Architecture (maps onto existing services)
- **`modelpilot/telemetry.py` (client):** extend `build_payload` to emit Stream-1 cells +
  Stream-2 outcomes (bucketing + k-anon suppression done locally before anything sends).
- **`ingest/` (vendor):** store cells; cross-customer rollup with k-anon (≥m customers) + optional
  DP; emit the **global prior table**.
- **`brain/`:** load the prior table; blend with per-customer floors in `_decision` (warm-start).
- **`console/`:** consent UI + a "fleet learning" panel ("you're contributing anonymized outcomes
  / here's the cold-start boost you're getting"); publish the schema.

## Honest risks & limits
- **Transfer isn't perfect.** A cell's safe tier mostly generalizes (small-context classification
  is Haiku-safe for most) but domain quality bars differ. That's why the prior is a *prior*, not a
  mandate — local validation always governs.
- **Re-identification if done naively.** Mitigated only by coarse buckets + k-anon + DP, not by
  good intentions. Build the suppression first; collect nothing until it's enforced.
- **Consent/legal.** Needs ToS/DPA language + a clear opt-in; counsel review before fleet
  collection goes live.
- **Paranoid-segment opt-out is fine** — they're still customers, still get the prior; the network
  effect doesn't require 100% participation.

## Build phases
1. **Schema + local bucketing + k-anon suppression** in `telemetry.py` (+ preview shows it). No
   collection yet — just the safe payload shape, fully tested.
2. **`ingest/` cross-customer rollup → global prior table** (k-anon ≥ m customers; DP optional).
3. **`brain/` warm-start blend** (prior + per-customer floors) with the safety invariant + tests.
4. **Console consent + fleet-learning panel + published schema.**
5. **ToS/DPA + counsel review** before flipping on real collection.
