# Outlay — internal security audit (June 2026) + remediation

*A control-by-control verification of our gov-readiness claims against the actual code and
tests — run adversarially (the goal was to **refute** claims, not confirm them). Each finding
lists its remediation status. Companion to `security-questionnaire.md`,
`nist-csf-self-assessment.md`, `incident-response-plan.md`, and `gov-tech-security-requirements.md`.*

**Baseline:** 224 tests passing (was 208; +16 added by this remediation). Docs-vs-code parity
restored — every claim below now either matches the code or is stated honestly as roadmap.

---

## Method
Five parallel reviewers each took a control family (auth/session, crypto/secrets, audit/logging,
data-boundary/RBAC/identity, accessibility/AI/cross-doc), verified each documented claim against
`console/` + `ingest/` source and the test that exercises it, and flagged any claim the code did
**not** back up. Findings are graded 🔴 critical / 🟠 medium / 🟡 low.

## What held up (verified, no change needed)
PBKDF2-HMAC-SHA256 **@ 200k iterations** + per-user salt · TOTP **RFC 6238** (HMAC-SHA1, step 30,
dynamic truncation, ±1 window) · lockout 5/900 per-identity → 429 · password breach-screening
(length>complexity, no forced rotation, HIBP k-anonymity env-gated) · session epoch enforced
per-request · RBAC owner/admin/member (members can't reach vendor-admin) · **metadata-only
serializer drops ticket title/body** · **read-only connectors (no write path)** · SSO/OIDC + SCIM
(real, tested) · configurable retention + self-serve erasure (real, tested) · TLS hygiene (no
`verify=False`, SSRF guard) · AI model/system/data card + AUP · accuracy genuinely computed ·
cross-doc honesty on SOC 2 / FIPS / Fly.io.

---

## Findings & remediation

| # | Sev | Finding | Resolution |
|---|---|---|---|
| **C1** | 🔴 | **Admin-enforced MFA gated owners only, not invited members** (`_require` excluded `member_id`). Members had no 2FA-enrollment path. | **Fixed in code** (follow-up build). Added per-member TOTP (AAL2): members table 2FA columns, member-aware `get_2fa`/`set_totp`/`verify_totp`/`disable_2fa`, a member second-factor challenge at login, and the `require_mfa` gate now covers **every principal** (member enrolls via `/app/security`). Tested (`test_member_totp_enroll_and_login_challenge`, `test_admin_mfa_policy_gates_members`). |
| **C2** | 🔴 | **The "incident/breach webhook posts a signed alert on a security event" did not fire** — `security_webhook` was a dead field; the signed-webhook machinery only carried spend/budget events. | **Fixed in code.** New `notify_security_event()` (HMAC-SHA256-signed, `x-outlay-signature`, per-account verifiable secret) fires from `_audit()` on every security action (failed login, lockout, MFA enable/disable, password reset, policy change, log-out-everywhere). Tested. |
| **C3** | 🔴 | **The 422 ingest boundary was field-NAME denylisting only** — a secret/prompt under an unlisted field name passed; console endpoints scanned top-level only. | **Fixed in code.** Added recursive `forbidden_payload_reason()` (any depth) with **credential-VALUE scanning** (`sk-`, `Bearer`, JWT, `ghp_`, `AKIA`, `AIza`, `xox*`) in both `console/store.py` and standalone `ingest/server.py`. Wired into `/api/meter`, `/api/proposals`, `/api/logs`, `/ingest`. **Doc-corrected** to describe it as name+value defense-in-depth atop the structural guarantee (not absolute content inspection). Tested. |
| **C4** | 🔴 | **"axe-core passes with zero violations" was unsubstantiated** — no a11y test existed; a real violation existed (placeholder-only input). | **Fixed in code.** Added `test_accessibility_structural_gate` (CI gate: programmatic name on every control, `alt`, `lang`, `title`) and fixed **~20 unlabeled controls** across auth/forgot/SSO-config/feedback/saved-views/account-deletion with `aria-label`. **Doc-corrected** to "automated structural gate in CI + manual axe-core spot-checks; independent VPAT on roadmap." |
| **M1** | 🟠 | **Three secondary secrets stored cleartext**: Slack/Teams webhook URL, SSO `client_secret`, webhook HMAC signing secret (the 5 tracker/provider tokens + TOTP secret were already encrypted). | **Fixed in code.** All three now routed through `secret_box` (Fernet) on write + decrypted at every read site. Tested (`test_secondary_connector_secrets_encrypted_at_rest`). |
| **M2** | 🟠 | **`secret_box` didn't fail safe** — with no key material it silently used a world-known default key. | **Fixed in code.** `_key()` now **raises** unless `CONSOLE_SECRETBOX_KEY`/`CONSOLE_SECRET` is set (explicit `CONSOLE_ALLOW_INSECURE_SECRETBOX=1` opt-in for bare dev). Tested. *(KDF strengthening left as a documented key-migration; the supported hardening is a KMS key.)* |
| **M3** | 🟠 | **Budget add/delete were not audited** (claimed under "program/budget changes"). | **Fixed in code.** `budget.add` / `budget.delete` audit events added. Tested. |
| **M4** | 🟠 | **Failed-login audit fired only for known accounts**; lockouts weren't audited. | **Fixed in code.** Lockout now emits `login.locked` (audit + SOC alert) for known accounts. *(Unknown-email probes have no tenant to attribute; the lockout throttle still rate-limits them.)* |
| **M5** | 🟠 | **Audit "≥90-day" claim was implicit**; full-account erasure wipes the audit log. | **Doc-corrected** (behavior is correct by design). Claims now: audit kept **life-of-account**, never auto-purged, spend-retention never touches it; **full-account erasure removes it** (right-to-be-forgotten) — with an IR note to preserve records for open investigations first. |
| **M6** | 🟠 | **"US data residency"** read as a present guarantee in one place; it's infra-dependent/roadmap. | **Doc-corrected** to: region is attestable in the Trust Center today; a contractually-guaranteed US-only residency ships with the FedRAMP-Moderate re-host. |
| **Low** | 🟡 | Test-coverage gaps: lockout-clears-on-success, absolute-session-timeout, password-change-revokes-sessions, audit rows for `2fa.*`/`password.reset`. | **Fixed** — tests added for all. |

---

## Remaining (tracked, not regressions)
- ~~**Member-MFA enrollment**~~ — ✅ **built** (per-member TOTP; `require_mfa` compels every teammate).
- ~~**WebAuthn/passkeys (FIDO2)**~~ — ✅ **built** for owners and members (enroll + passkey login +
  cloned-authenticator detection, via the vetted `py_webauthn` library). The phishing-resistant MFA
  upgrade is now shipped, not roadmap.
- **secret_box KDF** — current single-pass SHA-256 derivation is retained for backward-compat;
  hardening is the KMS-key path (`CONSOLE_SECRETBOX_KEY`) or a key-rotation migration.
- **Independent third-party VPAT** validation; **SOC 2 Type II**; the **FedRAMP-Moderate re-host** —
  the external/funded items unchanged from `gov-tech-security-requirements.md` §8(c).
