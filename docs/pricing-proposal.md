# Outlay — pricing proposal (concrete packaging)

Turns the analysis in `docs/pricing-research.md` into a concrete, sellable structure: named tiers,
price bands, what's in each, the savings-share add-on terms, and the regulated/gov premium. **These
are proposed anchors** — final numbers get set with the first 5–10 customers (per `TODO.md`), but a
concrete starting point beats negotiating from a blank page.

**The decided model (from the research):** a **hybrid** — a tiered **platform fee on AI spend under
management (SUM)**, sold as predictable flat annual bands, plus an **opt-in savings-share add-on**
tied to enforcement/commitment savings. **No per-seat.**

---

## 1. The value metric: AI spend under management (SUM)

We bill on the **annualized AI/LLM spend Outlay attributes and governs** — the thing whose value
scales with the customer's pain. It's measurable from day one (we compute it), aligns price to value,
and is the FinOps-category norm. The **% of SUM declines as spend grows** (like Finout/CloudZero),
because the marginal value flattens and large accounts won't pay a flat percentage.

Why not the alternatives (recap): **per-seat** punishes the team-wide read-only visibility that makes
us sticky and caps value at a few buyers; **pure %-of-savings** pays $0 until a customer enables
enforcement (most won't on day one) and underprices the always-on attribution/forecast/governance.

---

## 2. Platform tiers (annual, on AI spend under management)

| Tier | AI spend under mgmt (SUM) | Platform fee / yr | Effective % at top of band | Best for |
|---|---|---|---|---|
| **Team** | up to $500k | **$15,000** | 3.0% | first owner, single-stack, getting attribution + a forecast |
| **Growth** | $500k – $2M | **$36,000** | 1.8% | multi-provider, program budgets + governance in active use |
| **Scale** | $2M – $10M | **$90,000** | 0.9% | finance-owned, chargeback + commitment optimization |
| **Enterprise** | $10M+ | **Custom** (≈0.5–0.8%) | — | portfolio commitment optimization, SSO/SCIM at scale, premium support |

**Notes**
- Bands are **flat** within the range (predictable for finance/gov budgeting), stepping at the
  thresholds — not a live percentage meter.
- Effective % lands in the FinOps band (visibility tools ≈ 1–3% of spend) at small scale and **below**
  it at large scale, justified by the deeper value (work-item attribution + forecast + governance +
  commitment sizing) over pure visibility.
- **Annual prepay** assumed; monthly available at +15%. **Multi-year**: 10% off (2yr), 15% (3yr).

**What's included at every tier** (the always-on core — don't fragment it):
work-item attribution, own-data forecast + back-test, program budgets + pacing + variance, the
Commitments recommender (advisory), cross-provider ingest, read-only/BYOK/metadata-only posture,
audit logging + SIEM export, SSO/OIDC, 2FA/passkeys, RBAC.

**What steps up with tier:** SCIM provisioning + enforced MFA (Growth+), commitment **pacing &
renewal/negotiation pack** (Scale+), portfolio/multi-provider commitment optimization + premium
support SLA + custom retention (Enterprise).

---

## 3. The savings-share add-on (opt-in)

Keep the "we only win when you win" hook — but as an **add-on**, not the only model.

- **Terms:** **20% of measured net savings** Outlay causes — from (a) the enforcement gateway
  (route-down / caps, measured against a held-out **control arm**) and (b) realized **commitment**
  savings the recommender sized. Billed quarterly in arrears on **measured** savings only.
- **Differentiator vs. ProsperOps:** **no clawback, no early-termination penalty.** ProsperOps claws
  back unrealized savings-share for up to 12 months — a documented friction. We don't. Cancel the
  add-on anytime; you keep the savings.
- **Disarms the skeptic / lands pilots:** "Turn on enforcement and we only bill if a control arm
  proves we saved you money." It is *additive* to the platform fee, gated to where savings are real
  and attributable.
- **Guardrail:** never bill savings we didn't measure. The control arm / realized-commitment
  measurement is the integrity of the model (and a moat — owning a *measured* savings number the
  market lacks).

---

## 4. Regulated / government premium

Same platform, priced for the cost of serving a compliance buyer.

- **+25–50% on the platform fee** once the posture is sold as a SKU (the metadata-only / BYOK /
  read-only architecture that removes most control scope — see `docs/soc2-stateramp-sequencing.md`).
- Bundles: signed security questionnaire + Trust Center evidence, configurable retention, dedicated
  IR contact, and (as they land) **SOC 2 Type II → StateRAMP/GovRAMP** authorization.
- Higher ACV, longer cycle — run as a **parallel lighthouse** motion (Maryland), not the velocity
  wedge. Gate the premium on real certs; don't charge for compliance you haven't shipped.

---

## 5. Pilots & discounting

- **Pilot:** free, time-boxed (~2–4 weeks), read-only/metadata-only. Deliverable = a measured
  attribution-coverage % + a forecast back-test on the customer's own data. Converts to **Team** or
  **Growth** on a paid annual.
- **Design-partner discount:** up to **40% off year 1** for the first ~5–10 logos in exchange for a
  reference + product feedback. Sunset it deliberately — it's customer-acquisition spend, not the
  price.
- **Founder guardrails:** discount the *first year*, not the *list price*; never discount the
  savings-share % (it's already aligned); hold the line on the always-on core being un-fragmented
  (don't sell "attribution-only" cheap — it commoditizes the wedge).

---

## 6. Worked examples

- **Series-B dev-tools co, ~$1.2M/yr AI spend, multi-provider, no owner** → **Growth, $36k/yr**
  (3.0% effective). Enables enforcement in Q2 → savings-share add-on on measured cuts. Likely a
  $36k + variable ACV.
- **Scale-up, ~$6M/yr AI spend, finance-owned, wants chargeback + commitment sizing** → **Scale,
  $90k/yr** (1.5% effective). Renewal/negotiation pack drives a committed-spend deal → savings-share
  on the realized commitment savings.
- **State agency, ~$800k/yr, compliance-led** → **Growth + gov premium** (≈$45–54k/yr) once SOC 2 /
  StateRAMP evidence is in hand; pilot first.

---

## 7. Open decisions for the founder
1. **Anchor %** — are the 3.0% → 0.9% effective rates right for the value, or anchor lower to win the
   first logos fast and raise on renewal?
2. **Savings-share %** — 20% vs. the 15–35% category range; lower (15%) is a sharper "we only win when
   you win" wedge, higher captures more where we clearly cause savings.
3. **Core fragmentation** — keep attribution+forecast+governance bundled (recommended) vs. an
   entry "attribution-only" SKU to lower the entry price (risks commoditizing the wedge).
4. **SUM definition edge cases** — annualize from a trailing window? include seat-based AI (Copilot)
   in SUM or only consumption? (Recommend: consumption SUM is the metric; seats are context.)
5. **Publish vs. "talk to us"** — publish Team transparently (self-serve trust) and gate Growth+ to a
   call? The savings calculator (`/savings`) already primes the spend-based framing.

*All figures proposed/illustrative; validate willingness-to-pay with the first cohort before
hardening list prices. Keep every savings claim measured, never asserted.*
