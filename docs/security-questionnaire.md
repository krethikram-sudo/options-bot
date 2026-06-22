# Outlay — Security questionnaire responses (NIST 800-53 / SOC 2)

*Ready-to-paste answers for a state/enterprise security review. Every control maps to a
**shipped** feature with an in-product evidence location. Honest status is stated where we
don't yet hold a certification. Pairs with `gov-tech-security-requirements.md` (the bar) and
the in-product **Trust Center** (`/app/security`).*

---

## 0. Scope statement (read first — it answers half the questionnaire)

**Outlay is metadata-only, BYOK, and read-only.** It connects read-only to the customer's work
tracker and AI-provider usage APIs and processes **only metadata** — token counts, ticket IDs,
task categories, and dollar figures. **Prompt content, model outputs, and customer API keys
never leave the customer's environment.** No PII (beyond account login email), PHI, CJI, FTI, or
citizen data is ever transmitted to or stored by Outlay.

**Consequences for this review:**
- **FIPS 199 categorization: Low.** No high-water-mark data type is present.
- **Out of scope by architecture:** HIPAA, IRS Pub 1075 (FTI), FBI CJIS (CJI), PCI-DSS, FERPA,
  and FedRAMP High — Outlay never receives the data that triggers them. Our ingestion endpoints
  **reject any payload containing prompt text, outputs, or secret-looking keys (HTTP 422)** — the
  boundary is enforced, not just promised.
- Most "how do you protect [sensitive data]?" questions are answered by: *we never receive it.*

---

## 1. Access Control (NIST 800-53 **AC** · SOC 2 CC6)

| Control | Our answer | Evidence |
|---|---|---|
| **AC-2 Account management** | Accounts + invited members with lifecycle (invite → active → removed). SCIM 2.0 provisioning/de-provisioning. | Team page; `/scim/v2/Users` |
| **AC-3 / AC-6 RBAC & least privilege** | Role-based access: **owner / admin / member**. Members never inherit vendor-admin. Privileged actions gated to owner/admin. | Team page; nav/role checks |
| **AC-7 Unsuccessful logon attempts** | **5 failed logins → 15-minute lockout**, per identity (owners + members). | login throttle; lockout message |
| **AC-11 / AC-12 Session lock & termination** | Configurable **idle timeout** (sliding) and **absolute session lifetime**; **log-out-everywhere** revokes all other sessions immediately; a password change auto-revokes all sessions. | Trust Center → *Your sign-in security* |
| **AC-17 Remote access** | All access over **TLS** to a web app; no other ingress. Secrets transmitted only over TLS. | — |

---

## 2. Identification & Authentication (NIST 800-53 **IA** · NIST 800-63B · SOC 2 CC6.1)

| Control | Our answer | Evidence |
|---|---|---|
| **IA-2 MFA (all users)** | MFA supported for every user; **admin policy can require MFA org-wide** (users are gated to enroll before access). | Trust Center → *Organization security policy* |
| **IA-2 phishing-resistant / AAL2** | **TOTP authenticator (RFC 6238)** — AAL2, not a shared/phishable channel; email one-time codes also available. *(WebAuthn/passkeys is on the roadmap as the FIDO2 phishing-resistant upgrade.)* | Trust Center → *Set up authenticator app* |
| **IA-2(12) SSO** | **SSO via OIDC**, email-domain routed. | `/sso/start`, `/sso/callback` |
| **IA-5 Authenticator management (passwords)** | NIST 800-63B: **length over complexity**, no forced rotation, **screened against common/breached passwords** (bundled denylist + optional HIBP k-anonymity). Hashed with **PBKDF2-HMAC-SHA256 (200k iterations) + per-user salt**. | signup/reset validation |

---

## 3. Audit & Accountability (NIST 800-53 **AU** · SOC 2 CC7.2)

| Control | Our answer | Evidence |
|---|---|---|
| **AU-2 / AU-12 Auditable events** | Privileged + **authentication** events logged: logins, **failed logins**, 2FA enable/disable, password reset, member invite/role/remove, connection/identity changes, security-policy changes, **log-out-everywhere**, retention/purge, program/budget changes. | Activity page (`/app/audit`) |
| **AU-3 Content** | Each entry: timestamp, actor, action, detail. | Activity page |
| **AU-6 Review / AU-9 export** | **CSV export** of the full audit log for ingestion into your **SIEM**; an **incident/breach webhook** posts a signed alert to your SOC on a security event (supports your reporting SLA, e.g. Maryland's 1-hour MD-SOC rule). | `/app/audit/export.csv`; Trust Center webhook |
| **AU-11 Retention** | Audit log **retained ≥ 90 days** (kept indefinitely by default; data-retention controls govern *spend snapshots*, never the audit trail). | Trust Center status |

---

## 4. System & Communications Protection (NIST 800-53 **SC** · SOC 2 CC6.1/CC6.7)

| Control | Our answer | Evidence |
|---|---|---|
| **SC-8 In transit** | **TLS** for all client and integration traffic. | — |
| **SC-28 At rest** | Database at rest on the hosting platform; **connector secrets (tracker tokens, provider admin keys) are additionally encrypted at the application layer (Fernet/AES)** so a database-file leak alone never exposes them. | `secret_box`; schema comments |
| **SC-12 Key management** | App-layer key derived from a managed secret; **pluggable to a KMS-managed key** (`CONSOLE_SECRETBOX_KEY`) for a FIPS-validated module on a managed cloud — no code change. | `secret_box` |
| **SC-13 FIPS-validated crypto** | **Roadmap:** ships with the FedRAMP-Moderate cloud re-host (FIPS endpoints + validated KMS). Not required for the current FIPS-199-Low, metadata-only scope unless a contract cites it. | gov-tech doc §4 |
| **Boundary** | Outlay is **not a proxy/gateway** — AI calls go directly from the customer's infra to their provider. There is no request/response content in our path. | Security page → *Architecture* |

---

## 5. Incident Response (NIST 800-53 **IR** · SOC 2 CC7.3-7.5)

- **IR-8 plan:** documented IR process (separate runbook). **IR-6 notification:** a customer-set
  **incident/breach webhook** posts a signed alert to your SOC/SIEM on a security event, so you can
  meet your own notification SLA. We commit to contractual breach-notification timelines (e.g.,
  Maryland's 1-hour MD-SOC reporting; the state consumer-breach AG-first rule).
- Evidence: Trust Center → *Incident / breach notification webhook*.

---

## 6. Config / Risk / Contingency (CM, RA, CP · SOC 2 CC7.1/A1)

- **RA-5 Vulnerability scanning** *(process):* monthly dependency + image scanning; remediation
  SLAs **30 / 90 / 180 days** (High/Mod/Low). **CA-8 pen test** *(process):* annual third-party.
- **CM Configuration:** pinned dependencies; **secure SDLC (SSDF)**; SBOM available on request.
- **CP-9/10 Backups & recovery:** platform backups; documented, tested **RTO/RPO** *(process)*.
- These are operational commitments (the "infra/process track") rather than product features.

---

## 7. Media / Personnel / Data handling (MP, PS, privacy)

| Topic | Our answer |
|---|---|
| **Data retention / disposal** | Customer-**configurable retention** (keep, or auto-purge ingested spend data after 30/90/180/365 days) and **self-serve erasure** of ingested data or the entire account. |
| **Data residency** | US data residency; region is surfaced in the Trust Center. *(US-only hosting confirmed with the FedRAMP-Moderate cloud move; metadata-only scope doesn't trigger US-Persons-only staffing.)* |
| **PS-3 background checks** *(process)* | Personnel with data access undergo background screening. (No CJIS fingerprint requirement — no CJI in scope.) |
| **Tenant isolation** | Per-deployment isolation; metadata scoped to the customer's deployment. |
| **Sub-processors** | Hosting + email-routing sub-processors listed on request. |

---

## 8. AI governance (NIST AI RMF · MD AI Governance Act · OMB M-26-04)

- **Where AI is used:** only to **classify work into task categories** from ticket titles/labels and
  phrase short explanations — **no consequential decisions about people**.
- **Transparency artifacts:** an in-product **AI model & system + data card and Acceptable Use
  Policy** (Trust Center → *AI model & system card*), aligned to NIST AI RMF, Maryland's AI
  Governance Act, and federal M-26-04 (model/system/data cards + AUP).
- **No training on customer data;** every output is **explainable and human-correctable**; measured
  accuracy is reported in-product.

---

## 9. Accessibility (Section 508 / WCAG 2.1 AA / Maryland NTIAA)

- Built to **WCAG 2.1 AA / Section 508**; automated axe-core audit passes with **zero violations**;
  MFA offers a non-visual-access-compliant mechanism. **VPAT/ACR** available in-product (Trust
  Center → *VPAT / ACR*) and as a signed report on request.

---

## 10. Certifications & honest status

| Item | Status |
|---|---|
| **Architecture data-flow guarantee** (no sensitive data reaches us) | **In place & verifiable** — a property of the design |
| **At-rest secret encryption, MFA/TOTP, RBAC, audit + SIEM, lockout, session controls** | **Shipped** |
| **SOC 2 Type II** | **In progress** (the de-facto procurement gate) |
| **FedRAMP / StateRAMP-GovRAMP** | **Roadmap** — required only for GovRAMP-gated/federal deals; ships with the FedRAMP-Moderate cloud re-host; SOC 2 → Fast-Track |
| **FIPS 140-validated crypto** | **Roadmap** — with the managed-cloud move; not triggered by the current Low scope unless a contract cites it |

> We never claim what we don't hold. For a completed copy of your specific questionnaire, a SOC 2
> report when available, or a walkthrough of the data-flow boundary, contact
> **hello@outlay-ai.com**.
