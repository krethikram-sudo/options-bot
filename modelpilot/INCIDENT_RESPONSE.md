# Incident response & data-breach runbook (INTERNAL)

The operational backing for the commitments on `/security` and in the DPA ("notify without
undue delay"). Keep it short enough to actually follow under pressure. Owner: **[you]**
(security contact: krethikram@gmail.com). Review quarterly.

## What counts as an incident
Anything that may compromise confidentiality, integrity, or availability of the Service or
customer data: suspected unauthorized access, leaked credential/secret, vulnerability being
exploited, data exposure, prolonged outage, or a credible report from a researcher/customer.

**Reminder of what's at stake (and what isn't):** by design we **don't hold prompt content,
model outputs, or customer API keys** — so the blast radius of most breaches is account data +
aggregate metering, not customer prompts. State this accurately in any notice; don't over- or
under-claim.

## Severity (set fast, adjust later)
- **SEV-1** — confirmed unauthorized access to customer data, or a leaked production secret, or
  full outage. All-hands; customer notification likely.
- **SEV-2** — exploitable vulnerability, partial outage, suspected (unconfirmed) access.
- **SEV-3** — low-risk bug, single-account issue, researcher report with no active exploit.

## The loop (Detect → Contain → Eradicate → Recover → Notify → Learn)
1. **Declare & record.** Start a timestamped log (a shared doc/issue). Note who/what/when and
   assign an incident lead. Time matters for notification clocks — log everything.
2. **Contain.** Stop the bleeding before perfect understanding:
   - Leaked secret → **rotate immediately** (`CONSOLE_SECRET`, Stripe keys, SMTP, any provider
     key, SCIM/API tokens). Invalidate sessions if needed (rotating `CONSOLE_SECRET` does this).
   - Compromised account → suspend it (admin), revoke its API keys.
   - Active exploit → take the affected service offline or block the vector; the gateway
     **fails open**, so customer traffic still reaches Anthropic even if our brain is down.
3. **Eradicate.** Find and fix root cause (patch, close the hole, remove attacker access). Don't
   restore from a still-compromised state.
4. **Recover.** Restore service from clean state/backups (volumes: `consoledata`, `braindata`,
   `ingestdata`); verify integrity; watch for recurrence.
5. **Assess scope & notify** (below).
6. **Post-incident review** within ~5 business days: timeline, root cause, what worked, concrete
   fixes with owners/dates. Blameless.

## Notification (confirm exact obligations with counsel)
- **Customers:** if their personal data is affected, notify **without undue delay** (the DPA
  commitment). Include: what happened, when, data categories involved, what you've done, what
  they should do, and a contact. Don't speculate; correct as facts firm up.
- **Regulators / individuals:** breaches of personal data may trigger statutory timelines (e.g.
  GDPR's 72-hour authority notification; US state laws vary). **Have counsel determine if/when**
  — this runbook is operational, not legal advice.
- **Payment data:** Stripe holds card data; if Stripe is involved, follow their process.
- **Public/status:** post to `/status` for availability incidents; coordinate messaging.

## Drafting a customer notice (skeleton)
> Subject: ModelPilot security notice
> On [date] we [identified/were notified of] [what]. [Affected data / "no prompt content,
> outputs, or API keys were involved — those never reach our systems"]. We have [contained:
> rotated keys / suspended access / patched]. [What you should do, if anything]. We're [next
> steps]. Questions: krethikram@gmail.com. We'll update you as we learn more.

## Prevention checklist (keep current)
- Secrets in env/secret-manager, never in git; `.env` gitignored (it is).
- Rotate the **leaked Anthropic key** from earlier; rotate provider/Stripe/SMTP keys on schedule.
- Least-privilege access to prod; strong `CONSOLE_SECRET`; HTTPS + `CONSOLE_SECURE_COOKIES=1`.
- Regular volume backups; test a restore.
- Keep dependencies patched; watch the `/security` vuln-disclosure inbox.
- Tech E&O / cyber-liability insurance in place before prod customer traffic.
