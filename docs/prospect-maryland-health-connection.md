# Prospect dossier — Maryland Health Connection (MHBE)

Vendor-internal sales prep. Not customer-published. Compiled 2026-06-24 from public
sources (see `docs/gov-tech-security-requirements.md` for the underlying Maryland/
federal control research this builds on). Keep all claims honest — this buyer will verify.

---

## 1. One-page brief

**Who:** Maryland Health Benefit Exchange (MHBE) — an independent public-corporation
unit of Maryland state government (est. 2011, 9-member Board of Trustees) that operates
**Maryland Health Connection**, the state's ACA insurance marketplace. Enrolls **~1M+
Marylanders/year**; target uninsured rate < 5.5%.

**Spend shape:** ~**$42M/yr IT** (FY2026: $14.8M maintenance/support · $12.7M "MHC
enhancements" · $5.5M software licenses · $5.1M PM · $3.9M servers) + $13M call center.
Platform rebuilt on Connecticut's exchange tech via **Deloitte (~$43M)** after the failed
Noridian build (2014). Runs **Salesforce + Conga CLM**. **J29 Solutions** holds an IT
IDIQ master contract; other vendors: Technogen, Deloitte.

**Buyers / the room (sequence in this order):**
- **Dr. Venkat Koshanam — CIO** (technical fit; first call)
- **Scott Brennan — Director of Compliance & Privacy** (architecture sign-off; the gate)
- **Tony Armiger — CFO** (budget-governance ROI)
- Michele Eberle — Exec Director; Johanna Fabian-Marks — Deputy ED (ex-CMS)

**AI posture:** Early and governance-first. Maryland's **2025 AI Enablement Strategy**
(DoIT) + **AI Governance Act of 2024**; health/HHS agencies running low-risk AI PoCs with
recommendations due **Dec 2025 / Winter 2026**. No evidence of a large current LLM bill —
they are *writing the AI cost/governance playbook right now*.

**ICP-fit verdict:** Weak on *current AI spend* (not a Claude-heavy eng shop), **strong on
timing + architecture fit**. This is a **lighthouse government logo**, not the design-partner
pilot that validates coverage/forecast accuracy. Long procurement cycle; pursue as a
strategic logo that also forces the SOC 2 / StateRAMP investment we need regardless.

**Three angles:**
1. **AI-governance timing** — be the cost-governance + budget-guardrail layer as they
   operationalize the 2025 AI strategy (strongest).
2. **Architecture de-risk** — metadata-only + BYOK + read-only means **no PHI/PII/FTI ever
   reaches us**, taking Outlay *out of scope* for the data controls that disqualify most
   vendors. This is the whole pitch to Compliance.
3. **Vendor-spend attribution** — as Deloitte/J29 dev work adopts AI coding agents, the
   program-budget / earned-value feature shows AI-assisted dev cost per work item/project.

**Best wedge:** a **free, read-only, metadata-only pilot scoped to their development /
vendor AI usage** (not production PHI systems) — sidesteps the heaviest compliance, produces
a real artifact, rides the AI-strategy momentum.

---

## 2. Requirements → Outlay readiness (mapped to MHBE's frameworks)

Frameworks in play: **MARS-E 2.2 → ARC-AMPE** (CMS, aligns to NIST 800-53 Rev 5),
**IRS Pub 1075** (Federal Tax Information — exchanges verify income for subsidies),
**HIPAA**, **StateRAMP/GovRAMP**, **Maryland DoIT / NIST 800-53**.

Legend: ✅ have & can evidence · 🟡 configure/document · 🔴 real build / external / funded.

| Requirement | Status | Notes |
|---|---|---|
| Data minimization — no PHI/PII/FTI to vendor | ✅ | **By design** (metadata-only, BYOK, read-only). The single biggest scope-remover. |
| TLS 1.2+/1.3 in transit | ✅ | Standard HTTPS. |
| Encryption at rest | 🟡 | Connector tokens Fernet-encrypted (AES-128-CBC+HMAC); pluggable KMS hook (`CONSOLE_SECRETBOX_KEY`). **Caveat:** Fernet is not AES-256 nor FIPS-validated — see below. |
| FIPS 140-validated crypto (required by Pub 1075) | 🔴 | `cryptography`/Fernet is **not** a FIPS-validated module. Needs a FIPS build on a FedRAMP-authorized host. |
| MFA, incl. phishing-resistant (NIST 800-63 AAL2/3) | ✅ | TOTP **and** WebAuthn/passkeys (FIDO2) for owners + members. A genuine strength. |
| SSO (OIDC/SAML) + SCIM provisioning | ✅ | Shipped. |
| RBAC / least privilege | ✅ | Owner/admin/member/billing roles. |
| Audit logging + retention + SIEM export | ✅ | Audit log + CSV + `GET /api/v1/audit` (cursor) for Splunk/Datadog. |
| Session controls (idle/absolute timeout, revocation) | ✅ | Idle + absolute caps, epoch revocation, log-out-everywhere. |
| Incident response plan + breach notification | ✅ | IR plan (incl. Maryland 1-hour MD-SOC path) + HMAC-signed incident webhook to the customer's SOC/SIEM. |
| Configurable retention + right-to-erasure | ✅ | Per-account window + self-serve purge; account-delete purges encrypted creds. |
| Accessibility (Section 508 / WCAG 2.1 AA) | ✅ | Built to AA + **automated a11y CI gate** across the app + VPAT/ACR. Strong, evidenced. |
| AI transparency (NIST AI RMF) | ✅ | AI model/system/data card + AUP; no training on customer data. |
| Vulnerability scanning (monthly) + patch SLA | 🔴 | Not yet formalized as a recurring program. |
| Annual third-party penetration test | 🔴 | Not yet performed. External/funded. |
| SOC 2 Type II | 🔴 | In progress. **Highest-leverage single item** for this buyer. |
| StateRAMP/GovRAMP (Ready → Authorized) | 🔴 | Not started; mirrors FedRAMP Moderate; long (3PAO, ConMon, POA&M). |
| FedRAMP-authorized cloud (AWS GovCloud / Azure Gov) | 🔴 | Currently **Fly.io** — not FedRAMP-authorized. A re-host is the big architectural lift. |
| NIST 800-53 Rev 5 control evidence (MARS-E/ARC-AMPE) | 🟡 | NIST-CSF self-assessment exists; not a 3PAO assessment. Can produce a control-by-control SSP-style mapping. |
| Secure SDLC / SBOM | 🟡 | CI tests + reviews; SBOM not yet generated. |
| Personnel background checks | 🟡 | Small team; documentable as we grow. |

**Honest headline:** the metadata-only architecture removes the heaviest *data-handling*
scope (PHI/FTI/HIPAA), and we already satisfy most *operational* controls — MFA (incl.
phishing-resistant), SSO/SCIM, RBAC, audit+SIEM, session, IR, retention/erasure,
accessibility, AI transparency. The hard blockers are **attestations/authorizations**
(SOC 2 Type II, pen test, vuln-scan program, StateRAMP) and the **FedRAMP-authorized-cloud +
FIPS-validated-crypto re-host** — all external/funded/long. Lead with architecture-as-scope-
remover; be upfront that the attestations are on the roadmap.

**Pre-call prep checklist:**
- [ ] One-page security architecture diagram (data-flow showing metadata-only / no PHI).
- [ ] SOC 2 Type II timeline (target date) + StateRAMP-Ready intent.
- [ ] The MARS-E/ARC-AMPE → 800-53 control mapping with our "out-of-scope by data-flow" notes.
- [ ] Decide hosting answer: do we commit to an AWS GovCloud re-host if they advance?

---

## 3. Outreach email — to Dr. Venkat Koshanam (CIO)

> **Subject:** Cost governance for Maryland Health Connection's AI rollout — metadata-only, no PHI
>
> Dr. Koshanam,
>
> As MHBE operationalizes Maryland's 2025 AI Enablement Strategy, the question that
> usually surfaces right after "is it safe?" is "what is it costing us, and per what?" —
> especially across the vendor and enhancement work behind Maryland Health Connection.
>
> Outlay answers exactly that: it maps AI/LLM spend to the work that drove it, forecasts it,
> and holds it to budget. The reason I'm reaching out to a health exchange specifically is
> our architecture: Outlay is **read-only, bring-your-own-key, and metadata-only** — it sees
> token counts, ticket IDs, and dollar figures, never prompts, outputs, PHI, or FTI. By
> design, none of the data MARS-E / IRS 1075 / HIPAA govern ever reaches us, which keeps the
> integration out of the scope that stops most vendors at the door.
>
> We already support the operational controls your review will ask about — SSO/SCIM,
> phishing-resistant MFA (passkeys), RBAC, audit logging with SIEM export, configurable
> retention and self-serve erasure, an incident-response plan, and WCAG 2.1 AA with an
> automated accessibility gate. I'll be straight about where we are on the formal side:
> SOC 2 Type II is in progress and StateRAMP is on our roadmap, not yet complete — happy to
> share timelines and our NIST 800-53 control mapping up front.
>
> Would a 30-minute read-only pilot scoped to your **development / vendor AI usage** (not any
> production PHI system) be worth exploring? You'd get a concrete picture of AI-assisted
> delivery cost per project with zero data-handling risk, and it would dovetail with the AI
> governance work your team is delivering this winter.
>
> Worth a short call?
>
> — [Founder name], Outlay · outlay-ai.com

**Routing note:** if a cold email to the CIO doesn't land, the warmer path is via the
**J29 IDIQ** or another MHBE IT master-contract vendor, or a state-innovation/AI-strategy
contact at **Maryland DoIT** — government buys through existing vehicles.
