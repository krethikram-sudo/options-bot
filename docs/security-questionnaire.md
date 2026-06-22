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
  and FedRAMP High — Outlay never receives the data that triggers them. The privacy guarantee is
  primarily **structural**: the client sends only aggregates, and our serializer stores only
  metadata (token counts, ticket IDs, task classes, dollar figures) — ticket titles/bodies are
  dropped before storage. As **defense in depth**, the metadata/telemetry endpoints additionally
  **reject (HTTP 422) any payload that carries a sensitive field name** (`prompt`, `messages`,
  `content`, `output`, `api_key`, `authorization`, …) **or a string value matching a credential
  pattern** (`sk-…`, `Bearer …`, JWTs, cloud-provider keys) at any nesting depth.
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
| **IA-2 MFA (all users)** | MFA available to **every principal** — owners/admins (TOTP or email OTP) and **invited members (TOTP / authenticator app, AAL2)**. An **admin `require_mfa` policy gates every user** — owner, admin, and member — to enroll before app access (and challenges them for the second factor at each sign-in). SSO-provisioned members are additionally covered by the IdP's own MFA. | Trust Center → *Organization security policy* |
| **IA-2 phishing-resistant / AAL2** | **WebAuthn / passkeys (FIDO2)** — phishing-resistant, hardware-bound second factor (Touch ID / Windows Hello / security keys), with verified attestation/assertion and cloned-authenticator (sign-count) detection. **TOTP authenticator (RFC 6238)** also available (AAL2); email one-time codes as a fallback. Available to owners and invited members. | Trust Center → *Passkeys* / *Set up authenticator app* |
| **IA-2(12) SSO** | **SSO via OIDC**, email-domain routed. | `/sso/start`, `/sso/callback` |
| **IA-5 Authenticator management (passwords)** | NIST 800-63B: **length over complexity**, no forced rotation, **screened against common/breached passwords** (bundled denylist + optional HIBP k-anonymity). Hashed with **PBKDF2-HMAC-SHA256 (200k iterations) + per-user salt**. | signup/reset validation |

---

## 3. Audit & Accountability (NIST 800-53 **AU** · SOC 2 CC7.2)

| Control | Our answer | Evidence |
|---|---|---|
| **AU-2 / AU-12 Auditable events** | Privileged + **authentication** events logged: logins, **failed logins**, 2FA enable/disable, password reset, member invite/role/remove, connection/identity changes, security-policy changes, **log-out-everywhere**, retention/purge, program/budget changes. | Activity page (`/app/audit`) |
| **AU-3 Content** | Each entry: timestamp, actor, action, detail. | Activity page |
| **AU-6 Review / AU-9 export** | **CSV export** of the full audit log for ingestion into your **SIEM**; an **incident/breach webhook** fires an **HMAC-SHA256-signed** alert (`x-outlay-signature`) to your SOC on each security event — failed login, account lockout, MFA enable/disable, password reset, security-policy change, log-out-everywhere — supporting your reporting SLA (e.g. Maryland's 1-hour MD-SOC rule). | `/app/audit/export.csv`; Trust Center webhook |
| **AU-11 Retention** | Audit log **kept for the life of the account** — never auto-purged, and the configurable spend-data retention/auto-purge controls **never touch the audit trail**. (Full-account erasure removes it together with all tenant data, by design, to honor a right-to-be-forgotten request.) | Trust Center status |

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

- **IR-8 plan:** documented IR process (`incident-response-plan.md` + a private runbook). **IR-6
  notification:** a customer-set **incident/breach webhook** fires an HMAC-signed alert to your
  SOC/SIEM on each security event (failed login, lockout, MFA/password/policy change,
  log-out-everywhere), so you can meet your own notification SLA. We commit to contractual
  breach-notification timelines (e.g., Maryland's 1-hour MD-SOC reporting; the state consumer-breach
  AG-first rule). The webhook is a best-effort signal layered on an on-call human; it is not a
  substitute for a 24/7 staffed SOC (which we don't yet operate, and state plainly).
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
| **Data retention / disposal** | Customer-**configurable retention** (keep, or auto-purge ingested spend data after 30/90/180/365 days) and **self-serve erasure** of ingested data or the entire account. The audit trail is exempt from auto-purge (kept for the account's life). |
| **Data residency** | The configured region is **surfaced and attestable in the Trust Center**; today's hosting (Fly.io) is a US-based commercial cloud. A **contractually-guaranteed US-only residency** (region-pinned storage/processing) **ships with the FedRAMP-Moderate cloud re-host** — see `gov-tech-security-requirements.md` §4. Metadata-only scope doesn't trigger US-Persons-only staffing. *(Stated as roadmap, not a present guarantee.)* |
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

- Built to **WCAG 2.1 AA / Section 508**, with an **automated accessibility gate in CI** (every
  rendered form control has a programmatic name; images carry `alt`; pages declare language + title)
  plus manual keyboard/screen-reader and **axe-core** spot-checks. MFA offers a non-visual-access
  mechanism. **VPAT/ACR** available in-product (Trust Center → *VPAT / ACR*). *(An independent
  third-party VPAT validation — to drop the "self-assessment" qualifier — is on the roadmap before
  final state submission.)*

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
