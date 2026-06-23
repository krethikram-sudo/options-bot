# Outlay — cost to serve / KTLO (who pays for the compute, and how it scales)

*Vendor-internal. Answers: what does it cost **us** to run a customer's Outlay experience,
what does the **customer** pay for, and how does our cost-to-serve change per customer so we can
price accordingly. Live per-account + fleet numbers are on the admin console (`/admin` and
`/admin/accounts/{id}` → "Cost to serve (KTLO)"); the model is `console/cost_to_serve.py`.*

---

## The headline: there is no per-token COGS

**Outlay makes no server-side LLM calls.** Classification, forecasting, attribution, the cost
model, anomaly detection, and the new earned-value pacing are all **deterministic heuristics +
statistics** (`outlay/classify.py`: *"cheap, legible heuristics… a pure function of the work
item"*; the forecast is a class-stats model; the back-test is leave-one-out arithmetic). We never
send a prompt to Claude/GPT to deliver the product.

So our cost to serve is **infrastructure only**: CPU to rebuild the report on each sync, storage
of the report + history snapshots, a little egress, and transactional email — on top of one small
always-on machine. **The marginal cost of an additional customer, or of a heavier customer, is
cents-to-low-dollars per month.**

## Who pays for what

| Cost | Who pays | Notes |
|---|---|---|
| **The customer's AI provider bill** (Claude/GPT/etc.) | **Customer** | This is what Outlay *measures*, not what it incurs. BYOK — their key, their bill. |
| **Tracker + provider usage API calls** (Jira/Linear/GitHub, Anthropic Admin, Cursor) on each sync | **Customer** (their tokens/rate limits; admin reads are free) | Read-only metadata pulls. We don't pay for these. |
| **The routing gateway + on-box classifier** (`router_classify.py`) | **Customer's box** | Only if routing is un-parked; runs on their infra, never ours. |
| **Hosting** (Fly always-on `shared-cpu-1x`/512mb) | **Us** | The dominant *fixed* cost (~$2/mo), shared across all accounts. |
| **CPU to build reports on sync** | **Us** | Scales with data volume × sync frequency. Sub-cent on shared-cpu. |
| **Storage** (SQLite: report blob + history + audit + delivery rows) | **Us** | Scales with volume × sync frequency × retention. ~$0.15/GB-mo. |
| **Egress + transactional email** (webhooks, digests, alerts) | **Us** | Tiny; Resend ~$0.0004/send. |
| **Our Anthropic credits** | **Us** | Only for *internal* eval/golden-set/judge work — **not** customer-facing. Not part of per-customer KTLO. |

## How KTLO scales per customer (the pricing-relevant part)

Our cost-to-serve a given customer ≈ **data volume × sync frequency × retention × breadth**:

- **Data volume** — # tickets + usage events → report byte-size → storage + per-sync CPU.
- **Sync frequency** — `auto_sync_hours` (hourly → ~730 syncs/mo; weekly → ~4) → CPU + egress + the
  number of history snapshots stored.
- **Retention** — `retention_days` (90 vs 365 vs ∞) → how much history accumulates → storage.
- **Breadth** — # connectors, # webhooks, members → more pulls + outbound.

A **light** customer (small team, weekly sync, 90-day retention, 1 connector) and a **heavy** one
(enterprise volume, hourly sync, 365-day retention, several connectors + webhooks) differ by
**~100× in syncs and storage** — yet the heavy customer's *marginal* cost is still **a few cents a
month** (verified by the model + a test). The fixed always-on machine, amortized across active
accounts, is larger than any single customer's marginal cost until we scale up.

### Pricing implications
1. **Price on value, not cost-plus.** Gross margin is structurally ~99%+ at this scale — cost-to-serve
   is not the constraint. Anchor pricing to *spend under management / savings*, not our infra cost.
2. **But the cost axes are also the value axes**, so they make a clean, defensible **tier ladder**:
   volume (spend governed), freshness (sync cadence), retention, connectors, and enterprise breadth
   (SSO/SCIM/SIEM/webhooks). A *Starter* (weekly sync, 90-day retention, 1 connector) vs *Enterprise*
   (hourly, 365-day, many connectors + governance) tiers higher cost-to-serve **and** higher
   willingness-to-pay together.
3. **The real step-change is the scale ceiling, not per-customer cost.** The report is a JSON blob in
   SQLite on one machine. The cost curve is flat until volume forces a move to aggregate storage / a
   real DB / more machines — a *one-time* infra step (tracked as an open risk), not a per-customer cost.

## Where to see it
- **Per customer:** `/admin/accounts/{id}` → "Cost to serve (KTLO)" — loaded $/mo (marginal + fixed
  share), the storage/compute/egress/email breakdown, the cost drivers, the tier signal, and margin
  vs revenue.
- **Fleet:** `/admin` → "Cost to serve (KTLO) · all customers" — total loaded/marginal per month,
  average per account, the fixed base, and the most-expensive-to-serve accounts ranked.
- **Tunable assumptions:** unit costs are `CTS_*` env vars (Fly base, $/GB storage, $/email, $/vCPU-s,
  $/GB egress) — transparent, adjust to your real Fly invoice.
