# Government Tech & Security Requirements — Maryland State + Federal (Technical Readiness)

*Deep-research synthesis · June 2026. Companion to `maryland-gov-compliance.md` (procurement)
and `vpat-acr.md` (accessibility). This doc is the **technical control + security** view:
what Outlay must MEET, CONFIGURE, or BUILD — and a gap analysis against our current posture.*

**Product scope (sets the compliance bar):** metadata-only, BYOK, read-only FinOps SaaS for
AI/LLM spend. Processes token counts, ticket IDs, task categories, dollar figures only.
Prompts, model outputs, and customer API keys never leave the customer's environment. No
PII (beyond login credentials), PHI, CJI, FTI, or citizen data is transmitted to the vendor.
Hosted on Fly.io. Has SSO/OIDC, SCIM, 2FA, RBAC, audit logging + SIEM export, configurable
retention, self-serve erasure, WCAG 2.1 AA. **Not** yet SOC 2 Type II / FedRAMP / GovRAMP.

> **Verification note:** Many Maryland and federal primary PDFs (DoIT IT Security Manual,
> GovRAMP SAF, FedRAMP crypto policy, NIST 800-53B) block automated fetch (HTTP 403). Claims
> below are corroborated across multiple secondary sources that quote those primaries; exact
> integers and verbatim contract clauses should be confirmed against the primary PDFs before
> they go in a customer-facing security package. Per-claim confidence is noted.

---

## 0. TL;DR — the bar, and the one decision that matters

1. **Maryland does NOT mandate GovRAMP/StateRAMP** (unlike Arizona/Texas). It governs IT
   vendors through its **NIST-CSF-keyed Minimum Cybersecurity Standards + DoIT IT Security
   Manual + CATS+ contract clauses**. This is a *much* lower bar than a RAMP authorization, and
   it's the realistic near-term path to a Maryland deal. *(Confidence: med-high — confirm no
   agency-level GovRAMP ask with DoIT procurement.)*
2. **Our metadata-only / BYOK / read-only architecture is a genuine, structural advantage.**
   With no PII/PHI/CJI/FTI ever received, the system categorizes **FIPS 199 Low**, which removes
   the heavyweight regimes (CJIS, IRS-1075, HIPAA, FedRAMP High) from scope and, federally,
   qualifies for **FedRAMP-Tailored "LI-SaaS"** (~45–65 controls vs ~156). Most of the work is
   *proving* the posture, not *building* controls.
3. **The one real architectural decision: hosting.** **Fly.io is not FedRAMP/GovRAMP/StateRAMP
   authorized.** That is **disqualifying for federal** and for any **GovRAMP-gated state deal**,
   and even "LI-SaaS" still requires a **FedRAMP-authorized cloud underneath**. For **Maryland
   specifically** (no GovRAMP mandate, SOC-2-gated), Fly.io *may* pass — but re-hosting the
   government tenant on a **FedRAMP-Moderate commercial AWS/Azure region** is the medium-term
   unlock for federal + the ~26 GovRAMP states. *(Confidence: high.)*
4. **SOC 2 Type II is the single highest-leverage artifact** — not legally required, but the
   de-facto gate; it pre-answers ~half of any security questionnaire and feeds GovRAMP/TX-RAMP
   Fast Track later. Start it now (6–15 mo, ~$30–80k). *(Confidence: high.)*

---

## 1. Maryland-specific technical mandates (the binding ones)

Maryland flows requirements to vendors through **CATS+** (Consulting & Technical Services+, the
statewide IT master contract; **Functional Area 7 = Information System Security**) and **TORFP**
task orders, which **incorporate the DoIT IT Security Manual + MD-POL/MD-STD policy suite by
reference**. Key controls:

| Requirement | What Maryland requires | Confidence |
|---|---|---|
| **Incident reporting** | **Report to the MD-SOC within 1 hour** of confirming a cyber incident (up to 4h total if still triaging whether it's reportable). Per **MD-POL-209-01** Incident Response Policy. **This is the sharpest obligation — far stricter than the consumer-breach rule.** | High |
| **Encryption** | **Confidential/Restricted data (Data Classification Level 3+)** transmitted externally must be encrypted with state-approved tools; NIST-aligned. *(Exact cipher/FIPS citation not extractable from the 403'd PDF.)* — **Note:** Outlay's metadata is likely **Level 1–2**, so this heavy mandate may not even trigger. | High (obligation) / Med (exact spec) |
| **MFA** | Multi-factor auth required for digital-identity assurance; must offer at least one **Non-Visual Access (accessibility)-compliant** MFA mechanism. | High |
| **Framework** | **Minimum Cybersecurity Standards align to NIST CSF**; underlying control families from **NIST 800-53**. Agencies self-certify **annually (by Dec 1)** + bi-annual CSF maturity assessment (CMMI ≥1–2). Flows to vendors via procurement incorporation. | High |
| **Data ownership / return** | State data-ownership + return/destruction clauses standard in TORFPs. The **Maryland Data Privacy & Protection Act of 2026** newly forces **data-use agreements** into state contracts + requires agency privacy officers. | High (exists) / Med (verbatim) |
| **Consumer breach (PIPA, Commercial Law §14-3504)** | Separate, longer track: notify affected individuals **≤45 days** after investigation; **notify the Attorney General BEFORE individuals** (MD's distinctive "AG-first" rule); **encryption = safe harbor**. | High |
| **GovRAMP/StateRAMP** | **No confirmed Maryland mandate** as of June 2026 (contrast Arizona requiring GovRAMP/FedRAMP from July 2026). | Med-high |

Sources: [DoIT IT Security Policy](https://doit.maryland.gov/policies/ci/Pages/IT-Security-Policy.aspx) · [IT Security Manual v1.2](https://doit.maryland.gov/policies/ci/Documents/Maryland-IT-Security-Manual-v1-2.pdf) · [State Minimum Cybersecurity Standards](https://doit.maryland.gov/policies/ci/Pages/state-minimum-cybersecurity-standards.aspx) · [Incident Reporting (1-hr/MD-SOC)](https://doit.maryland.gov/policies/ci/Pages/cybersecurity-incident-reporting-requirements-for-state-governments.aspx) · [MD-POL-209-01 IR Policy](https://doit.maryland.gov/policies/ci/Documents/MD-POL-209-01-Incident-Response-Policy.pdf) · [CATS+](https://doit.maryland.gov/contracts/Statewide-Contracts/cats-plus/Pages/default.aspx) · [PIPA §14-3504](https://mgaleg.maryland.gov/mgawebsite/laws/StatuteText?article=gcl&section=14-3504) · [OAG PIPA guidance](https://oag.maryland.gov/i-need-to/Pages/Guidelines-for-Businesses-to-Comply-with-the-Maryland-Personal-Information-Protection-Act.aspx) · [GovTech: MD privacy → vendors](https://www.govtech.com/policy/maryland-expands-privacy-rules-for-state-agencies-vendors)

---

## 2. Federal baselines states inherit

States rarely write controls from scratch — they adopt these:

- **NIST SP 800-53 Rev 5** — the control catalog. Baselines: **Low ≈ 149**, **Moderate ≈ 287**,
  High ≈ 370 controls (incl. enhancements). **FIPS 199** categorizes a system Low/Moderate/High
  by impact to **Confidentiality/Integrity/Availability**, taking the **high-water mark**; that
  selects the baseline. Heaviest families for a low-impact SaaS: **AC, AU, IA, SC, IR, CM, RA, CP.**
- **NIST CSF 2.0** (Feb 2024) — six functions **Govern / Identify / Protect / Detect / Respond /
  Recover**; the new **Govern** function (incl. supply-chain risk) is what states increasingly use
  to frame **vendor risk** questionnaires. Maryland's Minimum Standards key to CSF.
- **GovRAMP (formerly StateRAMP; rebranded Feb 14, 2025)** — the state cloud-authorization program,
  built on **800-53 Rev 5**, mirroring FedRAMP. Levels: **Low ≈ 153**, **Moderate ≈ 319** controls
  (no High). Statuses: **Ready** (3PAO Readiness Assessment, ~80 mandatory controls — the entry
  milestone, no gov sponsor needed) → **Provisional** → **Authorized** (full 3PAO assessment +
  **penetration test**, **gov sponsor required**). **ConMon:** **monthly vulnerability scans** +
  POA&M + monthly PMO reporting. Fees ~$250/$500/$1,000 per month by revenue; full authorization
  typically **6–24 months** (or **weeks via Fast Track** with FedRAMP/SOC 2/ISO evidence).
  **~26 states** participate, often **partially / by agency** — membership ≠ blanket mandate.

Sources: [NIST 800-53B](https://csrc.nist.gov/pubs/sp/800/53/b/upd1/final) · [FIPS 199](https://csrc.nist.gov/pubs/fips/199/final) · [NIST CSF 2.0](https://www.nist.gov/cyberframework) · [GovRAMP rebrand](https://statetechmagazine.com/article/2025/04/stateramp-rebrands-to-govramp-perfcon) · [GovRAMP Ready](https://govramp.org/providers/ready/) · [GovRAMP 2026 modernization](https://govramp.org/blog/2026-program-modernization-and-adoption/) · [RAMP requirements by state](https://captaincompliance.com/education/ramp-requirements-by-state/)

---

## 3. The "numbers that bind" — operational controls states cite

These FedRAMP/800-53-derived thresholds are what appear in state security addenda:

| Control | Threshold | Source |
|---|---|---|
| **MFA** | Required for **all users** (privileged *and* non-privileged) — IA-2(1)/(2), both in the Moderate baseline. Phishing-resistant (FIDO2/PIV) pushed federally (OMB M-22-09). | NIST 800-53 IA-2 |
| **Identity assurance** | **AAL2** is the practical floor for moderate-impact gov systems w/ PII; IAL2 only for citizen identity-proofing. | NIST 800-63B |
| **Audit log retention** | **≥90 days hot** (FedRAMP AU-11); **12 mo hot + 18 mo cold** where OMB **M-21-31** applies. SIEM/central logging expected. | 800-53 AU; FedRAMP; M-21-31 |
| **Vulnerability scanning** | **Monthly** minimum, reported. | 800-53 RA-5; GovRAMP |
| **Penetration test** | **Annual**, independent 3PAO. | GovRAMP/FedRAMP ConMon |
| **Remediation SLAs** | **High/Critical 30 days · Moderate 90 · Low 180** (CISA-KEV items faster). | FedRAMP/GovRAMP RA-5 |
| **Incident notification** | FedRAMP CSP→customer **1 hour**; most state DPAs **24–72h**; **Maryland MD-SOC = 1 hour**. | FedRAMP; MD-POL-209-01 |
| **Backups / DR** | CP-9/10; **RTO/RPO defined, documented, tested annually** (no universal fixed number). | 800-53 CP; 800-34 |
| **Secure SDLC / SBOM** | Adopt SSDF (800-218). SBOM now **risk-based/discretionary** federally after **OMB M-26-05 (Feb 2026)** rescinded mandatory attestation — but still commonly *asked*. | EO 14028; M-26-05 |
| **Background checks** | PS-3 for staff w/ data access (fingerprint-based only if CJIS data — N/A for us). | 800-53 PS-3 |
| **Access / sessions** | Least privilege (AC-6), RBAC (AC-2), session timeout (~15 min common), lockout (3–5 tries). Password: **length > complexity, no forced rotation, breach-list screening** (800-63B). | 800-53 AC; 800-63B |

Sources: [IA-2(1)](https://csf.tools/reference/nist-sp-800-53/r5/ia/ia-2/ia-2-1/) · [OMB M-22-09](https://www.whitehouse.gov/wp-content/uploads/2022/01/M-22-09.pdf) · [FedRAMP AU-11](https://fedramp.scalesec.com/low/au-11/) · [M-21-31 summary](https://aws.amazon.com/blogs/publicsector/aws-federal-customers-memorandum-m-21-31/) · [FedRAMP scanning/SLAs](https://www.chainguard.dev/unchained/fedramp-vulnerability-scanning-requirements-explained) · [FedRAMP IR comms](https://www.fedramp.gov/docs/rev5/playbook/csp/continuous-monitoring/incident-communication/) · [OMB M-26-05 / SBOM](https://www.dwt.com/blogs/privacy--security-law-blog/2026/02/omb-changes-course-on-software-security) · [NIST 800-63B](https://pages.nist.gov/800-63-3/sp800-63b.html)

---

## 4. Cryptography & hosting (the decisive technical findings)

- **FIPS 140-2/140-3 validated modules** (NIST CMVP certificate — not just "AES") are the dividing
  line. Required when federal/regulated data is in play (FISMA, FedRAMP, IRS-1075, CJIS) via
  **800-53 SC-13**. For a metadata-only Low-impact state SaaS that doesn't touch FTI/CJIS, generic
  "strong/AES-256" language *may* be accepted — but this is shrinking and procurement-specific.
- **In transit: TLS 1.2 minimum** (1.3 preferred); **at rest: AES-256** — ideally via a
  FIPS-validated module. **Key management** (SC-12): documented lifecycle, KMS/HSM, rotation;
  customer-managed keys increasingly expected at Moderate.
- **Cloud:** Federal **requires a FedRAMP-authorized IaaS** underneath. **Commercial AWS/Azure at
  FedRAMP Moderate is acceptable** — **GovCloud is only needed for High / ITAR / US-Persons-only**.
  GovRAMP doesn't strictly force it but **caps you at "Provisional"** without it.
- **Fly.io:** has **SOC 2 Type 2 + HIPAA-ready (BAA) + ISO 27001 data centers**, **but no FedRAMP /
  GovRAMP / government region**. ⇒ **Disqualifying for federal; mostly disqualifying for
  GovRAMP-gated state deals; may survive a SOC-2-gated, low-sensitivity state procurement (e.g.,
  an initial Maryland deal).** *(A third-party site claiming "Fly.io FedRAMP compliant" is incorrect
  and was discarded.)*
- **Metadata-only relaxes scope but not the cloud floor:** Low categorization → **FedRAMP-Tailored
  LI-SaaS** (~45–65 controls), but LI-SaaS **still requires hosting on FedRAMP-authorized infra**
  and no PII beyond login credentials.

Sources: [800-53 SC-13](https://csf.tools/reference/nist-sp-800-53/r4/sc/sc-13/) · [FIPS 140-3](https://csrc.nist.gov/pubs/fips/140-3/final) · [FedRAMP impact levels](https://www.fedramp.gov/understanding-baselines-and-impact-levels/) · [AWS FedRAMP](https://aws.amazon.com/compliance/fedramp/) · [Fly.io compliance](https://fly.io/compliance) · [FedRAMP-Tailored LI-SaaS](https://tailored.fedramp.gov/) · [GovRAMP vs FedRAMP infra](https://www.wolterskluwer.com/en/expert-insights/hosting-alone-doesnt-equal-fedramp-govramp-compliance)

---

## 5. AI-specific governance

- **Maryland: EO 01.01.2024.02** (Jan 2024, Gov. Moore) + **AI Governance Act of 2024 (SB818,
  eff. July 1 2024)** — agencies must keep **annual AI inventories** and run **impact assessments
  for high-risk AI**, drawing on **NIST AI RMF**. Vendors of "high-risk AI" must supply the
  documentation that lets agencies complete those. (DoIT published a 2025 AI Enablement Strategy.)
- **NIST AI RMF 1.0** (Govern/Map/Measure/Manage) + **Generative AI Profile** (12 risk categories)
  — the referenced "responsible AI" standard; expect requests for model/system documentation,
  testing evidence, and a governance program.
- **Federal 2025–26 (volatile):** Biden's M-24-10/18 + EO 14110 were rescinded; replaced by
  **M-25-21/22** (Apr 2025: transparency/explainability docs, anti-vendor-lock-in, data/model
  portability, **no training on non-public gov data without consent**) and **M-26-04** (Dec 2025:
  LLM vendors must supply **model/system/data cards + an Acceptable Use Policy + feedback
  mechanism**, "truth-seeking/ideological-neutrality" — **material to contract eligibility/payment**).
- **Our angle:** we *route* third-party models (don't train), and prompts/outputs never reach us —
  so the model-card/AUP/no-training asks are largely satisfiable with documentation, and our
  privacy posture is ahead. NIST AI RMF alignment is a lead-with differentiator.

Sources: [MD EO 01.01.2024.02](https://governor.maryland.gov/Lists/ExecutiveOrders/Attachments/31/) · [SB818 fiscal note](https://mgaleg.maryland.gov/2024RS/fnotes/bil_0008/sb0818.pdf) · [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) · [M-25-22](https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf) · [M-26-04 analysis](https://www.crowell.com/en/insights/client-alerts)

---

## 6. SOC 2 Type II + how it relates to GovRAMP

- **Not legally required, but the de-facto procurement gate.** A current Type II pre-answers
  ~40–60% of a security questionnaire. **Trust Services Criteria → 800-53:** Security/Common
  Criteria (mandatory) maps to AC/AU/IA/RA/SC — the core government cares about; add **Availability**
  (CP) and **Confidentiality** (SI) for gov SaaS; **Privacy** only if PII-heavy (we're not).
- **Type II** = operating effectiveness over a window (first audit usually **6 months**);
  end-to-end **6–15 months**, **~$30–80k**.
- **Accelerates but doesn't substitute for GovRAMP.** GovRAMP/TX-RAMP **Fast Track** accepts
  existing **SOC 2 Type II / ISO 27001 / FedRAMP** packages as evidence to compress authorization.

Sources: [TSC↔800-53 crosswalk (AICPA)](https://www.aicpa-cima.com/resources/download/mapping-2017-trust-services-criteria-to-nist-800-53) · [SOC 2 & questionnaires](https://secureframe.com/blog/soc-2-vs-security-questionnaires) · [SOC 2 vs FedRAMP/GovRAMP](https://gocivix.com/resources/guides/how-soc-2-fedramp-stateramp-govramp-differ/)

---

## 7. How our architecture removes / reduces control scope

| Architecture choice | Scope it removes |
|---|---|
| **No PII/PHI/CJI/FTI received** | CJIS, IRS-1075, HIPAA, FedRAMP High **out of scope**; **FIPS 199 Low** → smaller 800-53 baseline → **FedRAMP-Tailored LI-SaaS** path. |
| **BYOK — customer keys never leave their box** | Removes key-custody/HSM liability for *customer provider keys*; the highest-risk secret never touches us. |
| **Read-only ingestion** | No write-path to customer systems → collapses a large class of integrity/abuse controls. |
| **Prompts & outputs never transmitted** | Satisfies the M-25-22 "no training on gov data" + the privacy core of the AI memos by construction. |
| **WCAG 2.1 AA already** | Section 508 / Maryland NTIAA nonvisual-access ahead of the typical vendor. |

This is the central sales argument: **we can truthfully answer "we never receive your sensitive
data,"** which zeroes out most questionnaire risk.

---

## 8. Gap analysis — three buckets (vs. our current posture)

### (a) Already satisfy — just **evidence** it
- MFA for all users (2FA) — IA-2 · SSO/OIDC + SCIM — IA/AC · RBAC / least privilege — AC-2/AC-6
- Audit logging + SIEM export — AU family · configurable retention + self-serve erasure
- TLS in transit + encryption at rest (via Fly) — SC-8/SC-28 *(FIPS-validation is the gap, see c)*
- WCAG 2.1 AA — §508 / NTIAA · Metadata-only/BYOK/read-only → Low categorization, removes CJIS/1075/HIPAA
- Honest "prompts/keys never leave" posture → most of the AI-privacy asks

### (b) Configure / document — modest effort, do now
- Set **audit-log retention ≥ 90 days hot** + written retention policy (AU-11)
- Write an **Incident Response Plan** (IR-8) with the **Maryland 1-hour MD-SOC** notification path + capability
- **Monthly vulnerability scanning** + patch SLAs (30/90/180) + an **annual third-party pen test**
- **Backup/DR** with defined + annually-tested **RTO/RPO** (CP-9/10)
- **Secure SDLC / SSDF** practices; generate an **SBOM** (asked even if not federally mandated)
- **Password/session policy** per 800-63B; **phishing-resistant MFA** (FIDO2/WebAuthn) for admins; **AAL2** docs
- **Personnel background checks** (PS-3) for staff with data access
- **AI artifacts:** model/system/data cards + an **Acceptable Use Policy** (AI RMF / M-26-04)
- **NIST CSF self-assessment** + a controls questionnaire response **mapped to 800-53**
- Finalize the **VPAT/ACR** (already drafted) and a **data-use-agreement / breach-terms** template
- **Start SOC 2 Type II** — the highest-leverage single item (6–15 mo)

### (c) Real build / architecture change — plan deliberately
- **Re-host the government tenant on a FedRAMP-Moderate commercial AWS/Azure region** — the unlock
  for federal + the ~26 GovRAMP states; not strictly required for an initial *Maryland-only*,
  SOC-2-gated deal, but the strategic blocker everywhere else. **Decide early.**
- **FIPS 140-2/3 validated cryptography** (FIPS endpoints + validated KMS) — comes largely with the
  authorized-cloud move
- **GovRAMP authorization** (Ready → Authorized) — only if a state RFP requires it; Authorized needs
  a **gov sponsor**; ~6–24 mo, or **weeks via Fast Track** once SOC 2/FedRAMP evidence exists
- **US-only data residency** guarantee

---

## 9. Recommended sequencing to be **Maryland-deal-ready**

Maryland's actual bar (no GovRAMP mandate; NIST-CSF + IT Security Manual + CATS+ clauses, SOC-2-gated)
means the near-term path is **paperwork + posture, not a re-platform**:

1. **Confirm the bar with DoIT procurement** — specifically: is any *agency-level* GovRAMP/FedRAMP
   ask in play, and what data classification do they assign a metadata-only tool? (Removes the only
   real uncertainty.)
2. **Lock the Maryland-binding controls now** (bucket b): IR plan with **1-hour MD-SOC** capability,
   ≥90-day audit retention, monthly scans + annual pen test, DR with tested RTO/RPO, MFA/AAL2 docs.
3. **Start SOC 2 Type II** in parallel (long pole; everything else feeds it).
4. **Finalize VPAT/ACR** (Maryland NTIAA nonvisual access) + **NIST CSF self-assessment** mapped to 800-53.
5. **Produce AI-governance artifacts** (model/system/data cards + AUP) for the AI Governance Act.
6. **Ready the contract terms** — data ownership/return, breach notification, data-use agreement,
   audit rights.
7. **Decide the hosting roadmap**: keep Fly.io for the Maryland pilot *if* DoIT confirms no GovRAMP +
   Low classification; **plan the FedRAMP-Moderate AWS/Azure migration** as the funded medium-term
   step that unlocks federal + GovRAMP states. Use **SOC 2 → Fast Track** to compress GovRAMP later.

**Cheapest/fastest wins first:** (1) confirm the bar, (2) IR/logging/DR config + VPAT, (3) SOC 2 kickoff
— before spending on a re-platform that Maryland may not require.

---

## Sources & confidence flags
- Primary Maryland docs (IT Security Manual v1.2, Minimum Standards, MD-POL/STD suite, CATS+ TORFPs,
  COMAR Title 21) and several federal PDFs (GovRAMP SAF v4.0, FedRAMP crypto policy, NIST 800-53B)
  **block automated fetch (403)** — corroborated via DoIT indexed summaries + multiple secondary
  sources. **Open the primaries to lock verbatim clause text before external use.**
- **Confirm with DoIT:** exact encryption/FIPS clause text, audit-log retention figure, CATS+
  data-return/audit-rights wording, the final bill number of the 2026 Data Privacy & Protection Act,
  and definitively no agency-level GovRAMP requirement.
- Federal AI policy (§5) is the **most volatile** area (2025–26 memo churn); the **state layer
  (Maryland, NIST AI RMF, SOC 2, GovRAMP) is the stable foundation** for the roadmap.
- The "Fly.io is FedRAMP compliant" third-party claim was **investigated and rejected** as incorrect.
