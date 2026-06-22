# Outlay — Incident Response Plan (IR-8)

*Satisfies NIST 800-53 **IR** family (IR-1, IR-4, IR-6, IR-8) and SOC 2 CC7.3–7.5. Built to
meet **Maryland's 1-hour MD-SOC** reporting obligation (MD-POL-209-01) when serving a Maryland
agency. Companion to `gov-tech-security-requirements.md` (the bar), `security-questionnaire.md`
(control mapping), and the in-product Trust Center incident/breach webhook.*

**Owner:** Security Lead (founder, until a dedicated role exists) · **Review cadence:** annual +
after any Sev-1/2 · **Last reviewed:** June 2026

---

## 0. Scope & why our exposure is small (read first)

Outlay is **metadata-only, BYOK, read-only**. Prompt content, model outputs, and customer API
keys **never leave the customer's environment**, and the ingestion boundary rejects any payload
containing prompt text, outputs, or secret-looking keys (HTTP 422). Consequently:

- **No PII (beyond login email), PHI, CJI, FTI, PCI, or citizen data** is ever stored by Outlay,
  so the **consumer-breach-notification** statutes (e.g. Maryland PIPA, §14-3504) are **rarely
  triggerable by construction** — the regulated data simply isn't here.
- The **realistic incident classes** are: (a) compromise of a **connector secret** (tracker token
  or provider *admin/usage-read* key — encrypted at rest via `secret_box`), (b) **account/session
  takeover**, (c) **availability** loss, (d) a **vulnerability** in our code or a dependency.
- This plan therefore centers on **credential/secret rotation, session revocation, and contractual
  customer/state notification**, not large-scale data-subject breach handling.

> **Highest-value contained asset:** customer connector secrets. Their compromise is the worst
> realistic case and drives the Sev-1 path below.

---

## 1. Definitions & severity

A **security incident** is any actual or suspected event that compromises the confidentiality,
integrity, or availability of Outlay or customer metadata, or any unauthorized access to a system,
account, or secret.

| Sev | Definition | Examples | Target response |
|---|---|---|---|
| **Sev-1 Critical** | Confirmed unauthorized access to production data/secrets, or a confirmed breach affecting a customer. | Connector-secret exposure; database exfiltration; admin-account takeover; secret committed to a public repo. | **Immediate**; IC paged; customer/state clock starts |
| **Sev-2 High** | Credible compromise not yet confirmed to have exposed data; significant control failure. | Repeated lockout-evading login attempts succeeding; a high/critical CVE actively exploitable in prod; MFA bypass. | **< 1 hour** to triage |
| **Sev-3 Moderate** | Security-relevant event, contained, no data exposure. | Single compromised member password (reset, no access); a high CVE not yet exploitable. | Same business day |
| **Sev-4 Low** | Minor / informational. | Failed-login spikes handled by lockout; low-severity dependency finding. | Routine remediation |

**Reportability triage:** if it's unclear whether an event is a reportable incident, treat the
**discovery time** as the clock start and resolve reportability **within the Maryland 4-hour outer
bound** (report to MD-SOC within **1 hour of confirmation**, up to 4 hours total while triaging).

---

## 2. Roles

- **Incident Commander (IC):** runs the response, declares severity, owns the timeline and the
  decision to notify. (Security Lead by default; documented backup.)
- **Technical Lead:** investigation, containment, eradication, recovery (may be the same person on
  a small team — the role still gets named in the log).
- **Communications Lead:** customer, state (MD-SOC), and internal notifications; keeps the
  notification clock.
- **Scribe:** maintains the incident timeline (often the IC on a small team).

On a founder-scale team one person may hold multiple roles; the plan still **names each role per
incident** so nothing is dropped.

---

## 3. Lifecycle (NIST 800-61 / IR-4)

### 3.1 Detection & reporting (IR-6)
**Sources:** the auth/security **audit log** (failed logins, lockouts, 2FA changes, password
resets, policy changes, connection/identity changes — `/app/audit`), the **incident/breach
webhook** (posts a signed alert to the customer's SOC/SIEM on a security event), platform/uptime
alerts, dependency/secret scanning, and inbound reports to **security@outlay-ai.com**.
**Anyone** who suspects an incident reports it to the IC immediately; there is no penalty for a
false alarm.

### 3.2 Analysis & triage
IC confirms scope: which accounts, which secrets, what data class (almost always *metadata only*),
and whether a customer/state notification obligation is triggered. Assign severity. **Start the
notification clock at discovery** for any plausible Sev-1/2.

### 3.3 Containment
- **Compromised connector secret:** revoke/rotate the affected token via the source provider;
  invalidate the stored secret; force re-connect. (Secrets are encrypted at rest, limiting blast
  radius of a DB-only leak.)
- **Account/session takeover:** force **log-out-everywhere** (bumps the session epoch, revoking all
  sessions), require password reset, require MFA re-enrollment if MFA state is suspect.
- **Vulnerability:** take the affected path out of service or ship a hotfix; rotate any exposed
  credentials.
- **Secret leaked to a repo:** rotate the secret immediately (rotation, not deletion, is the fix —
  assume it's already indexed), then purge.

### 3.4 Eradication & recovery
Remove the foothold, patch the root cause, restore from known-good (platform backups), and
**verify** the control that failed now holds (add a regression test where applicable). Return to
normal only after the Technical Lead and IC agree the threat is gone.

### 3.5 Post-incident (IR-4(1) / lessons learned)
Within **5 business days** of closing a Sev-1/2, hold a blameless review: timeline, root cause,
what detection/containment worked, and concrete follow-ups (with owners + dates). File the report;
fold preventive work into the backlog and, where it's a code/control gap, the **gov-readiness build
plan**.

---

## 4. Notification obligations (IR-6) — the clocks

| Audience | Trigger | Timeline | Mechanism |
|---|---|---|---|
| **Maryland MD-SOC** | Confirmed cyber incident affecting a Maryland-agency tenant | **Within 1 hour of confirmation** (≤4h total while triaging reportability) — per **MD-POL-209-01** | Direct contact per the agency's contract + the customer-set **incident/breach webhook** firing to their SOC |
| **Affected customer (contractual)** | Security incident affecting their tenant | Per contract (commit to **≤24h**, faster for confirmed exposure); we provide the webhook so the customer can meet *their* downstream SLA | Webhook signed alert + direct contact |
| **Consumer breach (MD PIPA §14-3504)** | Unauthorized acquisition of **personal information** | **AG-first**, then affected individuals **≤45 days** post-investigation — **expected to be N/A**: we hold no such PII; **encryption is a statutory safe harbor** | Only if ever triggered |
| **Internal** | Any Sev-1/2 | Immediate | IC pages team |

**Honest status:** the **webhook capability is shipped** (Trust Center → *Incident / breach
notification webhook*). The **MD-SOC direct-reporting path is a contractual/operational commitment**
activated per Maryland engagement — not a product feature. We do not currently hold a 24/7 staffed
SOC; the 1-hour capability is met by the webhook + an on-call founder/Security Lead, and this is
stated plainly to procurement.

---

## 5. Evidence & retention

- **Audit log** retained **≥90 days** (kept indefinitely by default; the audit trail is never
  governed by the spend-data retention controls). CSV export and SIEM stream available for the
  reviewing authority.
- Incident records (timeline, severity, actions, notifications, post-mortem) retained **≥1 year**.
- Chain-of-custody for any preserved artifacts noted in the incident record.

## 6. Testing & maintenance

- **Annual tabletop exercise** walking a Sev-1 connector-secret-compromise scenario end-to-end
  (detect → contain → rotate → notify within the 1-hour clock → recover → post-mortem).
- Plan reviewed **annually** and **after every Sev-1/2**; version + review date updated in the
  header.

---

## Appendix — quick-reference runbook (Sev-1 connector-secret compromise)

1. **Declare** Sev-1; IC named; **start the clock** (discovery time).
2. **Contain:** revoke/rotate the affected provider token at the source; invalidate the stored
   secret; force re-connect.
3. **Revoke sessions:** log-out-everywhere on any implicated account (epoch bump).
4. **Scope:** which tenant(s), which secrets, confirm **metadata-only** (no prompts/outputs/keys
   ever stored).
5. **Notify:** fire/confirm the incident webhook; contact the customer; if a **Maryland tenant**,
   report to **MD-SOC within 1 hour of confirmation**.
6. **Eradicate & recover:** patch root cause; restore known-good; add a regression test.
7. **Post-mortem** within 5 business days; file report; backlog the follow-ups.

> Contacts and the MD-SOC reporting endpoint are maintained in a private runbook, not in this
> repository (no secrets or contact details committed here).
