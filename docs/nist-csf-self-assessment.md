# Outlay — NIST CSF 2.0 Self-Assessment (mapped to 800-53 Rev 5)

*Self-assessment against the six **NIST Cybersecurity Framework 2.0** functions
(Govern / Identify / Protect / Detect / Respond / Recover), the structure Maryland's **Minimum
Cybersecurity Standards** key to. Each subcategory maps to the **800-53 Rev 5** control family a
reviewer expects and to **shipped** evidence. Pairs with `security-questionnaire.md` (control
detail), `incident-response-plan.md` (Respond/Recover), and `vpat-acr.md` (accessibility).*

**Scope:** metadata-only, BYOK, read-only FinOps SaaS. **FIPS 199 categorization: Low.** No
PII/PHI/CJI/FTI/citizen data received → CJIS, IRS-1075, HIPAA, FedRAMP-High out of scope.
**Status legend:** ✅ Shipped & evidenceable · 🟡 Partially in place / documented commitment ·
🛣️ Roadmap (sequenced with SOC 2 Type II + the FedRAMP-Moderate cloud move).

**Last reviewed:** June 2026 · **Maturity target:** CMMI ≥ 2 (Maryland Minimum Standards floor)

---

## GOVERN (GV) — the function states use to frame vendor risk

| Subcategory | Status | Our posture | 800-53 / evidence |
|---|---|---|---|
| **GV.OC** Organizational context | ✅ | Mission = honest AI-spend attribution; scope bounded by the metadata-only architecture. | Scope statement (questionnaire §0) |
| **GV.RM** Risk management strategy | 🟡 | Risk register maintained; FIPS-199-Low categorization drives a deliberately small control baseline. | RA-3; gov-tech doc §8 |
| **GV.RR** Roles & responsibilities | 🟡 | Security Lead named; IR roles defined per incident. | PS family; IR plan §2 |
| **GV.PO** Policy | 🟡 | Security/IR/retention policies documented; this assessment is the CSF-keyed policy artifact. | -1 controls (PL/PM) |
| **GV.SC** Supply-chain risk mgmt | 🟡 | Pinned dependencies; sub-processors (hosting, email) disclosed on request; SBOM available on request. | SR family; SA-12 |

## IDENTIFY (ID)

| Subcategory | Status | Our posture | 800-53 / evidence |
|---|---|---|---|
| **ID.AM** Asset management | ✅ | Small, enumerated asset set: console, brain, console DB, connector secrets. Data inventory = metadata only. | CM-8 |
| **ID.RA** Risk assessment | 🟡 | Threat model centers on connector-secret + account takeover; dependency/secret scanning. | RA-3, RA-5 |
| **ID.IM** Improvement | 🟡 | Post-incident reviews + gov-readiness build plan feed the backlog. | CA-5 (POA&M-style) |

## PROTECT (PR) — strongest function (where the product code lives)

| Subcategory | Status | Our posture | 800-53 / evidence |
|---|---|---|---|
| **PR.AA** Identity, auth & access control | ✅ | SSO/OIDC + SCIM; RBAC (owner/admin/member, least privilege); **MFA enforced for ALL principals** — owners/admins **and invited members** — via an org `require_mfa` gate; **TOTP (AAL2)** for everyone + email OTP for owners; **account lockout** (5→15 min); password breach-screening (800-63B, length>complexity, no forced rotation, HIBP optional); **session idle + absolute TTL + log-out-everywhere** (epoch). | AC-2/3/6/7/11/12, IA-2/2(1)/2(12)/5 |
| **PR.DS** Data security | ✅ | **TLS** in transit; DB at rest + **app-layer Fernet/AES encryption of connector secrets** (`secret_box`); **pluggable KMS key** hook for a FIPS module with the cloud move; configurable retention + self-serve erasure. | SC-8, SC-12, SC-28; MP-6 |
| **PR.PS** Platform security | 🟡 | Pinned deps; secure SDLC (SSDF); monthly dependency/image scanning *(process)*. | CM-2/6, SA-15 |
| **PR.IR** Tech infrastructure resilience | 🟡 | Platform backups; tenant isolation per deployment; US data residency surfaced in Trust Center. | CP-9, SC-7 |
| **PR.AT** Awareness & training | 🟡 | Security responsibilities documented; personnel with data access background-screened *(process)*. | AT, PS-3 |

## DETECT (DE)

| Subcategory | Status | Our posture | 800-53 / evidence |
|---|---|---|---|
| **DE.CM** Continuous monitoring | ✅ | **Auth + privileged-action audit log** (logins, **failed logins**, 2FA enable/disable, password reset, invites/role/removal, connection/identity, policy, log-out-everywhere, retention/purge, program/budget) → `/app/audit`, **CSV + SIEM stream**. | AU-2/3/6/12 |
| **DE.AE** Adverse-event analysis | ✅ | Lockout/throttle surfaces brute-force; **incident/breach webhook** fires HMAC-signed alerts to the customer SOC/SIEM on each security event (failed login, lockout, MFA/password/policy change, log-out-everywhere). | AU-6, IR-4, SI-4 |

## RESPOND (RS)

| Subcategory | Status | Our posture | 800-53 / evidence |
|---|---|---|---|
| **RS.MA** Incident management | 🟡 | Documented **Incident Response Plan** with severity model + IC roles. | IR-4, IR-8; `incident-response-plan.md` |
| **RS.AN/RS.MI** Analysis & mitigation | 🟡 | Containment runbook (secret rotation, session revocation, hotfix). | IR-4 |
| **RS.CO** Reporting & communication | 🟡 | **Incident webhook fires signed alerts on security events** (shipped); **Maryland 1-hour MD-SOC** reporting as a contractual/operational commitment (best-effort webhook + on-call human; no 24/7 SOC yet). | IR-6; IR plan §4 |

## RECOVER (RC)

| Subcategory | Status | Our posture | 800-53 / evidence |
|---|---|---|---|
| **RC.RP** Recovery execution | 🟡 | Restore from platform backups; documented RTO/RPO *(process; tested annually)*. | CP-10, CP-9 |
| **RC.CO** Recovery communication | 🟡 | Customer notified via webhook + direct contact through resolution. | IR-6 |

---

## Summary — three buckets (mirrors the gov-tech gap analysis)

**✅ Shipped & directly evidenceable (the PROTECT/DETECT spine):**
SSO/OIDC + SCIM, RBAC/least privilege, admin-enforced MFA + TOTP (AAL2), account lockout, password
breach-screening, session idle/absolute/log-out-everywhere, TLS + at-rest secret encryption,
auth-complete audit log with CSV/SIEM export, configurable retention + self-serve erasure, the
metadata-only/BYOK/read-only architecture (which holds us at FIPS-199 Low), and WCAG 2.1 AA.

**🟡 Documented commitments / process (do/keep doing):**
monthly vulnerability scanning + patch SLAs (30/90/180), annual third-party pen test, backup/DR with
tested RTO/RPO, SSDF + SBOM-on-request, PS-3 background checks, the IR plan's MD-SOC operational path,
and starting **SOC 2 Type II** (the highest-leverage artifact — pre-answers ~half of any state
questionnaire).

**🛣️ Roadmap — real build / architecture change:**
FedRAMP-Moderate AWS/Azure re-host (the federal + GovRAMP-state unlock; not required for an initial
Maryland-only, SOC-2-gated deal), FIPS 140-validated crypto (ships with that move), and GovRAMP
authorization only if a specific RFP requires it.

> **The honest framing:** the **PROTECT** and **DETECT** functions are largely **shipped product**;
> the remaining government bar is concentrated in **process/paperwork (RESPOND/RECOVER/GOVERN
> commitments) and one hosting decision** — not a re-platform — for the realistic near-term Maryland
> path. Confirm the exact bar (data classification, any agency-level GovRAMP ask) with DoIT
> procurement.
