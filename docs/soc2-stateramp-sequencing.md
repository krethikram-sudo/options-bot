# Compliance sequencing — SOC 2 Type II → StateRAMP

Vendor-internal. The plan for turning the controls we already operate into the
attestations enterprise + government buyers (incl. MHBE) require. Honest on cost,
time, and dependencies. Builds on `docs/gov-tech-security-requirements.md`,
`docs/nist-csf-self-assessment.md`, and the MHBE matrix in
`docs/prospect-maryland-health-connection.md`.

> **Bottom line:** **SOC 2 Type II is the single highest-leverage item** — it gates
> ~every enterprise deal and most state procurement, and it's a prerequisite/
> accelerator for StateRAMP. Do it first. **Do NOT** start the StateRAMP /
> FedRAMP-cloud re-host speculatively — it's 10× the cost and time; let a real,
> likely gov deal pull it. Our metadata-only / BYOK / read-only architecture is the
> lever that keeps scope (and therefore cost) small at every phase.

---

## What we already have (the starting line is not zero)

Operational controls shipped + evidenced: SSO (OIDC) + SCIM, phishing-resistant
MFA (TOTP + WebAuthn/passkeys), RBAC, audit logging + SIEM export, session
controls (idle/absolute/epoch revocation), IR plan (incl. MD-SOC 1-hr path) +
incident webhook, configurable retention + self-serve erasure, encryption at rest
(Fernet + pluggable KMS hook), WCAG 2.1 AA + automated a11y CI gate, NIST AI RMF
card, NIST-CSF self-assessment. **Most of the SOC 2 Security criteria are already
operating** — the gap is formalization, third-party attestation, and a few process
controls (vuln scanning, pen test, background checks, SBOM/secure-SDLC docs).

---

## Phase 0 — Evidence what exists (now · ~$0 · mostly us)

Make the existing controls answerable *today*, before any auditor is engaged.
- Control narrative / lightweight SSP mapping our controls → SOC 2 TSC and NIST
  800-53 Rev 5 (reuse the CSF self-assessment; the MHBE matrix is the seed).
- Trust Center already exists (VPAT, AI card, security page) — keep it current.
- **Outcome:** we can pass security questionnaires and have a credible "SOC 2 in
  progress, here's our control map" answer on a first sales call.

## Phase 1 — SOC 2 readiness + Type I (0–3 mo · ~$15–30k)

1. **Compliance automation platform** — Vanta / Drata / Secureframe (~$7–25k/yr).
   Automates evidence collection + monitors controls continuously. Pick one.
2. **Close the gap controls** (mostly eng + policy, we can do most):
   - Monthly **vulnerability scanning** + dependency audit in CI (pip-audit /
     Trivy / Dependabot) with a patch SLA.
   - **SBOM** generation in CI; documented **secure SDLC**.
   - Formal **policy set** (access, change mgmt, incident response, vendor mgmt,
     BCP/DR, data classification) — templated by the platform.
   - **Background-check** process for personnel (documentable as we hire).
3. **Third-party penetration test** (~$8–25k) — required evidence + gov asks for it.
4. **SOC 2 Type I** (point-in-time) — a CPA firm attests controls are *designed*
   correctly. Issued in ~6–10 weeks; gives a report to show buyers while Type II's
   observation window runs.

## Phase 2 — SOC 2 Type II (3–9 mo · ~$15–30k more)

- A **3–6 month observation window** during which the automation platform collects
  evidence that controls *operate* effectively, then the auditor issues the **Type
  II report**. This is the artifact enterprises and states actually want.
- **Total realistic first-year all-in: ~$30–60k** (platform + auditor + pen test),
  **~5–9 months** to a Type II report (Type I in hand by ~month 2–3).

## Phase 3 — StateRAMP / GovRAMP (gated on a real gov deal · 9–24 mo · $100k+)

Only start when a government opportunity (e.g. MHBE) is advancing to procurement.
- **Prerequisite: re-host to a FedRAMP-authorized cloud** (AWS GovCloud or Azure
  Government). This is the big eng lift — and it also delivers **FIPS 140-validated
  crypto** (via the cloud KMS/HSM) and **US-person/US-region** data residency,
  closing the IRS-1075/MARS-E encryption + hosting gaps in one move.
- **GovRAMP "Ready" → "Authorized"** via a **3PAO** assessment against NIST 800-53
  (FedRAMP Moderate baseline), with continuous monitoring (monthly scans, POA&M).
- **Scope lever:** push hard that Outlay is **metadata-only / no PHI / PFI / FTI**,
  so we categorize **low-impact** and argue many control families are out of scope
  by data-flow. "Ready" may suffice for some state buys; confirm with the agency.
- **Cost/time:** $100k–500k+ and 12–18+ months depending on scope and the re-host.

---

## Cost & timeline at a glance

| Phase | What | When | Cost | Who |
|---|---|---|---|---|
| 0 | Evidence existing controls + SSP map | now | ~$0 | us |
| 1 | Platform + gap controls + pen test + **SOC 2 Type I** | 0–3 mo | ~$15–30k | us + vendor + auditor + pen tester |
| 2 | **SOC 2 Type II** (observation window) | 3–9 mo | ~$15–30k | auditor + platform |
| 3 | GovCloud re-host + **StateRAMP** (deal-gated) | 9–24 mo | $100k–500k+ | us (re-host) + 3PAO |

## What's code/eng (we can do) vs external/funded

- **Eng / in-repo:** vuln-scan + dependency-audit CI, SBOM, secure-SDLC + policy
  docs, the SSP/control mapping, evidence hooks for the platform, and (Phase 3) the
  GovCloud re-host + FIPS-crypto wiring.
- **External / funded:** compliance-automation subscription, CPA auditor (Type I/II),
  pen-test firm, and (Phase 3) the 3PAO.

## Decision gates (don't skip)

1. **Start Phase 1 now if** any enterprise/gov deal is real — SOC 2 pays for itself
   on the first one and you need it regardless.
2. **Type II before StateRAMP** — never the reverse; Type II evidence accelerates a
   3PAO assessment.
3. **Phase 3 only on a signed/likely gov deal** — the re-host + 3PAO is too expensive
   to fund speculatively, and the metadata-only architecture may let the agency
   accept SOC 2 + "GovRAMP Ready" rather than full authorization. Ask before building.

## Immediate next actions (this week)

- [ ] Pick a compliance-automation platform (demo Vanta + Drata).
- [ ] Stand up vuln scanning + dependency audit + SBOM in CI (cheap, we control it).
- [ ] Draft the SOC 2 / 800-53 control-mapping doc from the CSF self-assessment.
- [ ] Get 2–3 pen-test quotes; schedule once Phase-1 controls are in.
- [ ] Decide Security-only vs +Confidentiality TSC scope (BYOK/metadata-only argues
      a tight scope).
