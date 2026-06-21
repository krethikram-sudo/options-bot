# Selling Outlay to Maryland State Government (DoIT) — the Bar to Clear

*Compliance & procurement readiness assessment · researched June 2026.*
*Product scope assumed: metadata-only, BYOK, read-only FinOps SaaS for AI/LLM
spend. No PII/PHI/CJI/FTI ever transmitted to the vendor by design. Hosted on
Fly.io. SSO/OIDC, SCIM, 2FA, RBAC, audit logging + SIEM export, configurable
retention, self-serve erasure, built to WCAG 2.1 AA. Not yet SOC 2 or
FedRAMP/StateRAMP authorized.*

---

## TL;DR — the realistic bar

Outlay's architecture is genuinely favorable for state-gov sales: because **no
regulated data (PII/PHI/CJI/FTI/citizen data) ever leaves the customer's box**,
the heavyweight data-handling regimes (CJIS, IRS 1075, HIPAA, FedRAMP High) are
**out of scope** as long as we hold that line contractually. The work is mostly
*proving* the posture, not *building* new controls.

**Three buckets:**

- **(A) Hard blockers to even transact** — business registration in Maryland +
  eMMA/eMaryland Marketplace Advantage vendor registration; the mandatory state
  contract terms (data ownership, breach-notification timelines, data return,
  audit rights); cyber/tech-E&O insurance at the contract's required limits; and
  a **VPAT/ACR** demonstrating Nonvisual Access (Maryland NTIAA) + WCAG/§508
  conformance. None of these require a certification audit — they're paperwork +
  insurance + an accessibility report we can largely produce now.
- **(B) Commonly required / will be asked for** — **SOC 2 Type II** (the single
  most-requested artifact; expect it as a near-default), the state's **Minimum
  Cybersecurity Standards** / NIST 800-53-aligned controls questionnaire, and
  increasingly **GovRAMP (formerly StateRAMP) Moderate or FedRAMP reciprocity**
  for cloud services touching state data. These are the real spend/time items.
- **(C) Differentiators we're already ahead on** — metadata-only + BYOK +
  read-only means we can truthfully answer "we never receive your sensitive
  data," which collapses most security-questionnaire risk. WCAG 2.1 AA built-in
  beats the typical vendor who scrambles for a VPAT late. NIST AI RMF alignment
  + transparency is a live procurement ask for AI tools and we can lead with it.

**Recommended sequence (cheapest/fastest first):**
1. **VPAT 2.5 / ACR** (WCAG 2.1 AA + §508 + Nonvisual Access) — days/weeks, we're built for it.
2. **Maryland business + eMMA vendor registration**; line up **cyber + tech-E&O insurance** ($1M–$5M typical).
3. **SOC 2 Type II** — 3–6 mo observation window; start the clock now, it gates the most deals.
4. **GovRAMP/StateRAMP "Ready" → "Authorized" (Moderate)** *or* lean on **FedRAMP reciprocity** — only if a specific deal/DoIT master contract demands it. Most expensive/slowest; defer until a real opportunity needs it.

---

## 1. Security & compliance frameworks — required vs. triggered

| Framework | Status for us | Why |
|---|---|---|
| **SOC 2 Type II** | **Commonly required (B).** Not a statute, but the de-facto entry ticket. Start the audit clock. | Standard state-gov + enterprise security-review expectation. Reciprocity input to GovRAMP. |
| **GovRAMP / StateRAMP** (rebranded Feb 2025) | **Situational (B/C).** Optional today, trending mandatory; Moderate increasingly asked for AI tools touching state data; FedRAMP Moderate often accepted under reciprocity. | [secureframe](https://secureframe.com/blog/govramp), [BetaQuick](https://betaquick.com/blog/stateramp-vs-fedramp-ai-compliance/) |
| **FedRAMP** | **Not required** for state procurement; only if a federal flow-down or a FedRAMP-authorized underlying cloud is demanded. | State, not federal, buyer. |
| **NIST 800-53 / CSF / FISMA** | **Indirect (B).** Maryland's state security standards are 800-53-aligned; expect a controls questionnaire, not a certification. | [DoIT State Minimum Cybersecurity Standards](https://doit.maryland.gov/policies/ci/Pages/state-minimum-cybersecurity-standards.aspx) |
| **NIST AI RMF** | **Differentiator (C).** Live ask for AI vendors; we align (transparency, metadata-only, risk posture). | Maryland AI EO + DoIT Responsible AI policy. |
| **CJIS** | **Out of scope** — no criminal-justice data ever transmitted. | BYOK/metadata-only. |
| **IRS Pub 1075 (FTI)** | **Out of scope** — no federal tax info. | BYOK/metadata-only. |
| **HIPAA** | **Out of scope** — no PHI; no BAA needed if we never receive PHI (hold contractually). | BYOK/metadata-only. |
| **PCI-DSS** | **Out of scope** — no cardholder data. | BYOK/metadata-only. |
| **FERPA** | **Out of scope** — no education records. | BYOK/metadata-only. |

**The architecture argument to make in every security review:** prompt content,
model outputs, and API keys never leave the customer environment; we process
only task categories, token counts, ticket IDs, and dollar figures. That removes
us from the scope of the data-type-triggered regimes above — but only if the
contract and our data-flow diagram state it explicitly. Keep the line honest.

## 2. GovRAMP / StateRAMP specifics

- **Rebrand:** StateRAMP → **GovRAMP** (Feb 2025), expanding to all levels of
  government. ([secureframe](https://secureframe.com/blog/govramp))
- **Mandate status:** currently **optional but expected to become mandatory**;
  state agencies increasingly require **Moderate** for AI deployments handling
  state data/PHI, with **FedRAMP Moderate often accepted under reciprocity**.
  ([BetaQuick](https://betaquick.com/blog/stateramp-vs-fedramp-ai-compliance/))
- **Levels:** Ready → Authorized; Low / Moderate / High impact. For a
  low-impact, metadata-only tool, **"Ready" (or SOC 2 + a security package)** is
  often enough to start; full **Authorized Moderate** is the expensive end —
  defer until a specific DoIT contract requires it.
- **No Maryland-specific public mandate found** naming GovRAMP as a hard gate as
  of mid-2026 — confirm directly with DoIT for the specific vehicle.

## 3. Accessibility — a genuine hard blocker (A)

- Maryland's **Nonvisual Access (NTIAA)** law + **COMAR 14.33.02** require IT
  procured by the state to be accessible to users with disabilities; vendors
  supply a **VPAT/ACR** mapping conformance to **WCAG 2.1 AA / §508**.
- **We're built to WCAG 2.1 AA** — so this is a fast, cheap win and a
  differentiator. Produce a **VPAT 2.5 (or 2.5Rev) ACR** covering WCAG 2.1 AA,
  §508, and explicit Nonvisual Access statements. Back it with an axe-core audit
  (we already run one).

## 4. Procurement mechanics

- **eMaryland Marketplace Advantage (eMMA)** is the mandatory state e-procurement
  portal — **register as a vendor** to bid/receive awards.
- **DoIT master contracts / CATS+** (Consulting & Technical Services) and
  cooperative vehicles (**NASPO ValuePoint**) are common SaaS on-ramps;
  riding an existing vehicle is faster than a net-new solicitation.
- **Small-dollar / pilot paths** exist below formal-bid thresholds — ideal for a
  paid pilot via the CEO relationship, avoiding a full RFP initially.
- **Small Business Reserve (SBR)** registration may help if we qualify.
- **Mandatory contract terms to expect:** state data ownership, **breach
  notification timelines**, data return/portability on termination, audit
  rights, e-discovery/records retention (MPIA), indemnification, and limitation
  of liability. Our metadata-only scope makes most of these easy to accept.

## 5. Data residency / sovereignty

- Expect a **US-hosting / US data-at-rest & in-transit** requirement and
  encryption (TLS in transit, AES-at-rest). Fly.io can pin US regions — confirm
  and document region pinning. A metadata-only vendor still typically must meet
  US-residency for the metadata it does store. If a deal demands a
  FedRAMP-authorized underlying cloud, that's a Fly.io constraint to flag early.

## 6. Privacy & breach-notification law

- **Maryland Online Data Privacy Act (MODPA)** — effective **Oct 1, 2025**;
  enforcement from **Apr 1, 2026** (cure period to Apr 1, 2027). Applies at
  35,000-consumer / 10,000-with-sale thresholds; requires data minimization,
  reasonable security, DPAs, and consumer-rights handling. Our metadata-only,
  no-citizen-data posture keeps exposure low, but the **"reasonable security"**
  and **data-protection-assessment** duties still inform our contract reps.
  ([McNees](https://www.mcneeslaw.com/maryland-data-privacy-law/),
  [OneTrust](https://www.onetrust.com/blog/marylands-online-data-privacy-act-modpa-key-rules-and-requirements/))
- **Maryland Personal Information Protection Act (PIPA)** — breach-notification
  law. Critical for our contract: as a **third-party that maintains but does not
  own** the data, notification to the owner is **"as soon as reasonably
  practicable, but no later than 10 days"** after discovery; consumer notice
  within **45 days**; AG notice before consumer notice. We must be able to commit
  to the **10-day vendor timeline** contractually.
  ([MD OAG](https://oag.maryland.gov/i-need-to/Pages/Guidelines-for-Businesses-to-Comply-with-the-Maryland-Personal-Information-Protection-Act.aspx),
  [Justia §14-35](https://law.justia.com/codes/maryland/commercial-law/title-14/subtitle-35/))
- **MPIA (Public Information Act):** anything we hand the state may be subject to
  public-records requests; avoid embedding anything sensitive in deliverables.

## 7. AI-specific governance

- **Gov. Wes Moore EO 01.01.2024.02** (Jan 8, 2024) on responsible/productive AI
  use in state government; **DoIT Responsible AI Policy** and the state's **AI
  Enablement Strategy** (Jan 2025) push **transparency, risk assessment, and
  NIST AI RMF alignment** from AI vendors. We should publish a short **AI
  transparency / model-use statement**: Outlay classifies metadata only, doesn't
  train on customer data, and the customer's keys/prompts never leave their box.
  This is a **lead differentiator** for an AI-cost tool sold to a state AI program.

## 8. Insurance & corporate

- **Cyber liability + technology E&O** (often bundled as "tech E&O") are
  routinely mandated; Maryland gov contracts commonly require **$1M–$5M** limits
  scaled to contract size/risk, plus general liability.
  ([Insureon — MD E&O](https://www.insureon.com/small-business-insurance/professional-liability/maryland),
  [DH Lloyd — MD gov contractor](https://www.dhlloyd.com/business-insurance/specialized-business-insurance/maryland-government-contractor-insurance))
- **Corporate:** register the entity to do business in Maryland (SDAT), good
  standing, W-9, and eMMA vendor profile.

---

## Recommended sequence & rough effort

| # | Action | Effort / cost | Gating? |
|---|---|---|---|
| 1 | **VPAT 2.5 / ACR** (WCAG 2.1 AA + §508 + Nonvisual Access) | Low — we're built for it | Hard blocker (A) |
| 2 | **MD entity + eMMA registration**, W-9, good standing | Low | Hard blocker (A) |
| 3 | **Cyber + tech-E&O insurance** ($1M–$5M) | Low–med, recurring | Hard blocker (A) |
| 4 | **SOC 2 Type II** — start observation window now | Med, 3–6 mo | Commonly required (B) |
| 5 | **Security package**: data-flow diagram, NIST 800-53 / state Minimum Cybersecurity Standards questionnaire, AI transparency statement | Med (mostly writing) | Commonly required (B) |
| 6 | **GovRAMP "Ready" → Authorized (Moderate)** *or* FedRAMP reciprocity | High, slow | Only if a specific vehicle demands it — defer |

**Bottom line:** Maryland is a realistic target. The metadata-only/BYOK/read-only
architecture removes the hardest regimes; the near-term work is a VPAT, vendor
registration + insurance, and starting SOC 2. GovRAMP/StateRAMP is the only
heavy item, and it can wait for a concrete opportunity. Lead the conversation
with "your sensitive data never reaches us, and we're WCAG-AA + NIST-AI-RMF
aligned" — that is genuinely ahead of the typical vendor.

### Sources
- [GovRAMP overview — Secureframe](https://secureframe.com/blog/govramp)
- [StateRAMP vs FedRAMP for AI — BetaQuick](https://betaquick.com/blog/stateramp-vs-fedramp-ai-compliance/)
- [Maryland DoIT — State Minimum Cybersecurity Standards](https://doit.maryland.gov/policies/ci/Pages/state-minimum-cybersecurity-standards.aspx)
- [MODPA explainer — McNees](https://www.mcneeslaw.com/maryland-data-privacy-law/)
- [MODPA key rules — OneTrust](https://www.onetrust.com/blog/marylands-online-data-privacy-act-modpa-key-rules-and-requirements/)
- [Maryland PIPA business guidance — MD OAG](https://oag.maryland.gov/i-need-to/Pages/Guidelines-for-Businesses-to-Comply-with-the-Maryland-Personal-Information-Protection-Act.aspx)
- [Maryland PIPA statute (§14-35) — Justia](https://law.justia.com/codes/maryland/commercial-law/title-14/subtitle-35/)
- [Maryland E&O insurance — Insureon](https://www.insureon.com/small-business-insurance/professional-liability/maryland)
- [Maryland government contractor insurance — DH Lloyd](https://www.dhlloyd.com/business-insurance/specialized-business-insurance/maryland-government-contractor-insurance)
