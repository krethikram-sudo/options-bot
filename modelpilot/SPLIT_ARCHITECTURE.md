# Split architecture — protect the IP, push updates instantly (design)

## Problem
Running entirely in the customer's environment gives us our best feature (their
API keys and prompts never leave their network) but two real drawbacks:
1. **Copyability** — anything that ships can be read and copied.
2. **Update distribution** — improvements require the customer to `git pull` /
   reinstall; we can't push fixes or better routing to everyone at once.

## Core idea
Split the product into two pieces:

- **Local proxy (ships to the customer)** — thin, "dumb" plumbing. Terminates the
  customer's `ANTHROPIC_BASE_URL`, forwards requests to Anthropic with the
  customer's key (key never leaves their box), records the ledger locally, serves
  the dashboard. Contains almost no IP. ~The boring 20%.
- **Routing brain (we host)** — the valuable, hard-to-copy 80%: the classifier,
  the per-category policy, the calibration, the continuously-learned weights. The
  local proxy asks the brain "what should I do with this request?" and gets back a
  decision.

```
customer app ─► local proxy ─────────────────► api.anthropic.com   (prompt + key, unchanged)
                     │  features only (no prompt text)
                     └─► ModelPilot routing brain (hosted)  ─► {model, confidence, gate}
```

## What crosses the wire to us — and what never does
**Sent:** derived, non-sensitive features only — token counts, the category/
difficulty signals, has_tools / has_structured_output, cache state, session id
(hashed), the requested model. Essentially today's `extract_features()` output
**minus the prompt text**.
**Never sent:** prompt text, response text, API keys. This preserves the entire
privacy story ("keys and content stay in your environment"); we receive metadata,
the same shape we already store in the local ledger.

## Fail-open (non-negotiable)
If the brain is slow or unreachable, the local proxy falls back to the bundled
local heuristics (today's `router.py`) — or, more conservatively, to "stay on the
requested model." The customer's traffic is **never** blocked by our service being
down. This keeps the "no behavior change / kill switch" guarantee intact and means
our uptime is not in their critical path.

## What this solves
- **IP protection:** the classifier/policy/calibration never ship. A copy of the
  local proxy is worthless without the brain (and the brain is gated by license).
- **Instant updates:** we improve routing server-side; every customer benefits
  immediately, no pull/redeploy. This is also where cross-customer learning
  compounds (aggregate, privacy-preserving signal → better labels for everyone).
- **Metering & control:** the brain authenticates each call (license token), so we
  meter usage, see who's running, and revoke instantly — a much stronger gate than
  the in-client check.

## Latency
The routing decision is ~0.05 ms locally today. Adding a network hop to the brain
costs one round-trip; mitigations: (a) co-locate / regional endpoints, (b) cache
the decision per (category, session) so follow-ups are local, (c) decide
asynchronously in shadow/guidance (no hot-path impact), (d) fail-open immediately
on timeout. Net target: a few ms p95, negligible vs multi-second generation.

## Relationship to the license gate
The in-client HMAC gate (`license.py`) is the beta stopgap. The split architecture
*subsumes* it: once the brain is the gatekeeper, autopilot simply can't run without
a valid, server-validated, revocable token — no client-side secret to extract.

## Migration path (incremental, low-risk)
1. **Now (beta):** all-local + in-client license gate + strong LICENSE terms.
2. **v1:** extract a `decide()` client interface in the proxy with two backends —
   `local` (today) and `remote` (calls the brain). Ship with `local` default;
   opt-in `remote`.
3. **v2:** stand up the hosted brain (stateless decision endpoint + token auth +
   policy store). Flip design-partner deployments to `remote`, `local` as fallback.
4. **v3:** cross-customer learning in the brain; the local heuristics become the
   fail-open floor only.

## Open questions
- Self-hosted brain option for security-strict customers (on-prem appliance under
  license) vs. our managed endpoint — likely offer both.
- Exactly which features are safe to transmit (privacy review before v2).
- Decision caching keys and TTL to keep the added latency invisible.
