# Gov-readiness — product build plan (what to BUILD)

*Engineering punch-list derived from `gov-tech-security-requirements.md`, grounded in an
audit of the actual console code (June 2026). Separates **product build** (code we write)
from **infra/process** (hosting, audits, paperwork — not features).*

## ✅ Status — all product gaps built (208 tests passing)
Shipped: #1 admin-enforced MFA · #2 TOTP authenticator (WebAuthn/passkeys is the remaining
phishing-resistant upgrade) · #3 session idle timeout + epoch + log-out-everywhere · #4 account
lockout + login throttle · #5 password breach screening (+ optional HIBP) · #6 auth-event audit
completeness · #7 audit retention floor ≥90d + incident webhook · #8 Trust Center (policy +
sign-in security + VPAT/AI-card artifacts) · #9 pluggable KMS key hook in `secret_box` (FIPS
module ships with the cloud move) · #10 data-residency statement. The infra/process track (§B)
is unchanged.

## The honest framing
Most of the government bar is **process, paperwork, or a hosting move** — not product code.
The console already has the security spine: **SSO/OIDC, SCIM, RBAC, 2FA, audit logging +
SIEM/CSV export, configurable retention, self-serve erasure, and at-rest secret encryption
(Fernet via `secret_box`)**, plus the metadata-only/BYOK/read-only architecture that keeps us
at FIPS-199 **Low**. So the **product** gaps are a focused set of **auth/session hardening +
a trust surface** — a few weeks of work, not a re-platform.

---

## A. Product build gaps (code) — prioritized

| # | Build | Why / control | Have today | Effort |
|---|---|---|---|---|
| 1 | **Admin-enforced MFA** (org policy: "require MFA for all members," block app until enrolled) | MFA for **all** users — IA-2(1)/(2), the single most-cited gov ask. We only have per-user *opt-in* 2FA. | 2FA opt-in only | **S–M** |
| 2 | **Phishing-resistant / stronger MFA**: add **TOTP** (authenticator app) and ideally **WebAuthn/passkeys** (FIDO2) | 800-63B **AAL2** + the federal phishing-resistant push (M-22-09). Today's email/SMS **OTP is phishable**. | email/SMS OTP | **M** (TOTP) / **M–L** (WebAuthn) |
| 3 | **Session idle timeout + shorter absolute TTL** + "log out everywhere" | AC-11/AC-12, AC-2(5). Today the session is a **14-day absolute** cookie with **no idle timeout** — too long for gov. | 14-day absolute, no idle | **S–M** |
| 4 | **Account lockout + login/OTP rate-limiting** | AC-7. **None today** — no lockout after failed logins, no throttle on login/OTP. | none | **S–M** |
| 5 | **Password breach-list screening** (HIBP k-anonymity) on signup/reset | 800-63B (length>complexity + screen against known-breached). Today only a **min-8** check. | min-8 only | **S** |
| 6 | **Audit-log completeness for auth events**: log **failed logins**, 2FA enable/disable, password change/reset, SSO/SCIM provisioning, settings + account-deletion + billing changes | AU-2/AU-3/AU-12 want **auth failures** + security-relevant events. Current `_audit` covers app actions but **misses auth-failure + 2FA/password events**. | partial | **S** |
| 7 | **Audit-log retention floor (≥90 days) + configurable + customer SIEM stream** | FedRAMP AU-11 (≥90 days hot). We keep audit logs **indefinitely** (fine), but it's implicit; make it explicit with a **≥90-day floor** and an optional **push to customer SIEM** (not just CSV pull). | CSV export; implicit-forever | **S** (floor) / **M** (push) |
| 8 | **Trust Center surface** — extend `/app/security` with downloadable **compliance artifacts** (VPAT, SOC 2 when ready), the **AI model/system/data cards + Acceptable Use Policy**, and a customer-set **security/incident contact + breach-notification webhook** | AI Governance Act + federal M-26-04 (model/data cards, AUP); supports hitting Maryland's **1-hour MD-SOC** notification via a customer-side alert hook. | `/app/security` page exists | **M** |
| 9 | **KMS-backed, FIPS-validated secret encryption** — swap `secret_box`'s Fernet (AES-128, env-derived key, **not FIPS-validated**) for a **FIPS-validated module + KMS-managed key** | SC-12/SC-13 — only strictly required at the **federal/GovRAMP** tier; comes largely with the authorized-cloud move. | Fernet at-rest enc | **M** (ships with cloud move) |
| 10 | **Data-residency pinning + statement** (US-only storage/processing) | Residency expectations. Mostly **infra** (US region), small app/config + a surfaced statement. | infra-dependent | **S** (app) |

**Already satisfied — do NOT rebuild (just evidence):** SSO/OIDC, SCIM, RBAC (owner/admin/member),
2FA mechanism, audit log + CSV/SIEM export, configurable retention, self-serve account/data
erasure, **at-rest secret encryption**, TLS in transit, WCAG 2.1 AA, metadata-only/BYOK/read-only.

---

## B. NOT product build (so we scope it right) — infra / process / paperwork
- **Re-host the gov tenant on a FedRAMP-Moderate AWS/Azure region** (infra project) — the unlock
  for federal + GovRAMP states; *not* required for an initial Maryland-only, SOC-2-gated deal.
- **SOC 2 Type II** audit · **annual penetration test** · **monthly vulnerability scanning** ·
  **DR runbook + RTO/RPO testing** · **GovRAMP authorization** (if a state requires it).
- **Policies/paperwork:** Incident Response Plan (with the 1-hour MD-SOC path), NIST CSF
  self-assessment mapped to 800-53, VPAT/ACR finalization, data-use-agreement + breach-terms
  templates, personnel background-check process.

---

## C. Recommended build order
1. **#5 breach-screen, #4 lockout/rate-limit, #3 session idle timeout** — small, high-signal hardening that any security questionnaire / SOC 2 will check. *(Quick wins, ~days each.)*
2. **#1 admin-enforced MFA, #6 audit auth-events** — the most-cited control (MFA-for-all) + the audit completeness SOC 2/AU expect.
3. **#2 TOTP then WebAuthn/passkeys** — phishing-resistant MFA; TOTP first (cheap), passkeys next.
4. **#8 Trust Center** (compliance artifacts + AI model/data cards + AUP + incident-contact hook) — directly serves the AI Governance Act + M-26-04 + Maryland breach-notice.
5. **#7 SIEM push, #10 residency statement** — as deals ask.
6. **#9 KMS/FIPS crypto** — sequence with the FedRAMP-cloud migration (don't do it standalone).

**First sprint suggestion (1–2 weeks):** #3, #4, #5, #6, #1 — the auth/session/logging hardening
that makes us pass a state security questionnaire and seeds the SOC 2 evidence, with **no
hosting change required**. The FedRAMP-cloud move (B) is the bigger, separately-funded track.
