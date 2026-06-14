#!/usr/bin/env python3
"""Replay a small, realistic mixed-difficulty workload through the Maven
gateway so the digest/dashboard show a representative savings number.

It simulates a customer who defaults *everything* to one expensive model
(--baseline, default Opus) — exactly the over-provisioning Maven exists to
fix. Each request goes through the gateway to the real Anthropic API, so it
costs a little real money (small max_tokens keeps it to cents). The gateway
records token usage; `modelpilot digest` then reads it.

Run the gateway in 'advise' (see decisions, model unchanged) or 'autopilot'
(actually route) so the per-request decision headers are visible:

    MODELPILOT_DB="$HOME/modelpilot/modelpilot.db" \
        modelpilot gateway --mode advise --port 8410

    export ANTHROPIC_API_KEY=sk-ant-...
    export ANTHROPIC_BASE_URL=http://127.0.0.1:8410
    python scripts/seed_demo_traffic.py            # baseline = claude-opus-4-8
    python scripts/seed_demo_traffic.py claude-fable-5

    modelpilot digest --days 1
"""
import os
import sys

import httpx

# A representative *ICP* workload: a support/document-ops pipeline, which is
# what Maven targets — mostly cheap, routable tasks (triage, extraction,
# summarization, drafting) with a few genuinely hard ones that correctly stay
# on the top model. This mirrors where real customer spend is routable, so the
# number is representative rather than a worst case.
PROMPTS = [
    # --- cheap support/doc tasks: route to Haiku ---
    "Classify this support ticket's sentiment as positive, negative, or neutral: 'Been waiting 3 days for a reply, getting frustrated.'",
    "What priority is this ticket — low, medium, or high? 'Production is down for all users.'",
    "Is this message spam or abuse? 'WIN a FREE iPhone!!! click bit.ly/xyz now'",
    "Extract the order number and email from: 'Order #A-48217 never arrived, reach me at lee@acme.io.'",
    "Extract the invoice number, amount, and due date from: 'Invoice INV-2042 for $3,180 is due 2024-05-01.'",
    "Translate this support reply to Spanish: 'Your refund has been processed and will arrive in 3 to 5 days.'",
    "Summarize this ticket thread in two sentences: 'Customer cannot log in; reset email not arriving; confirmed correct address; escalated to the auth team.'",
    "Summarize this release note in one line: 'v4.2 adds SSO, fixes a CSV export crash, and improves dashboard load time by 40%.'",
    "Reformat these notes as bullet points: follow up with vendor, renew SSL cert, archive Q1 logs.",
    "Tag the intent of this message (billing, technical, sales, or other): 'Can I upgrade to the annual plan and get a discount?'",
    "What does an HTTP 429 response from an API mean?",
    "Make this reply more concise and professional: 'hey so um the thing you asked about is basically done i think, lmk'.",
    "Extract the action items from these meeting notes: 'Decided to ship beta Friday. Sam to write docs. Priya to set up billing.'",
    "What language is this written in? 'Bonjour, je voudrais annuler mon abonnement.'",
    "Classify this review as a bug report, feature request, or praise: 'Would love a dark mode option.'",
    "Summarize the key point of this policy: 'Refunds are available within 30 days of purchase for unused annual plans.'",
    # --- mid: should hold at Sonnet ---
    "Draft a short customer-facing status-page update: API latency was elevated for 25 minutes and is now resolved.",
    "Write a SQL query to count orders per customer in the last 30 days from an orders(id, customer_id, created_at) table.",
    # --- hard: should stay on the top model ---
    "Design a data-retention and deletion architecture for GDPR across a multi-service system with an audit trail.",
    "Debug an intermittent race condition: two workers occasionally double-process the same queue job under load. Likely causes and fixes?",
]


def main():
    base = os.environ.get("ANTHROPIC_BASE_URL", "http://127.0.0.1:8410").rstrip("/")
    key = os.environ.get("ANTHROPIC_API_KEY")
    baseline = sys.argv[1] if len(sys.argv) > 1 else "claude-opus-4-8"
    if not key:
        sys.exit("Set ANTHROPIC_API_KEY (the gateway forwards it upstream).")
    if "PASTE" in key or "..." in key or key in ("your-key", "sk-ant-"):
        sys.exit("ANTHROPIC_API_KEY is still the placeholder — paste your real key "
                 "(starts with sk-ant-) and re-run.")
    if "127.0.0.1" not in base and "localhost" not in base:
        print(f"WARNING: ANTHROPIC_BASE_URL={base} is not the local gateway — "
              "traffic won't be measured.")

    headers = {"x-api-key": key, "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    print(f"Replaying {len(PROMPTS)} prompts through {base} (baseline={baseline})\n")

    routed = errors = 0
    for i, prompt in enumerate(PROMPTS, 1):
        body = {"model": baseline, "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]}
        try:
            r = httpx.post(f"{base}/v1/messages", json=body, headers=headers, timeout=120)
        except Exception as e:  # noqa: BLE001
            errors += 1
            print(f"[{i:2}/{len(PROMPTS)}] request failed: {e}")
            continue
        if r.status_code != 200:
            errors += 1
            print(f"[{i:2}/{len(PROMPTS)}] HTTP {r.status_code}: {r.text[:120]}")
            continue
        cat = r.headers.get("x-modelpilot-category", "?")
        action = r.headers.get("x-modelpilot-action", "")
        rec = r.headers.get("x-modelpilot-recommended-model", "(shadow: hidden)")
        conf = r.headers.get("x-modelpilot-confidence", "")
        if action == "switch":
            routed += 1
        print(f"[{i:2}/{len(PROMPTS)}] {cat:22} {action:7} -> {rec:20} {conf}")

    print(f"\nDone. {routed}/{len(PROMPTS)} would route to a cheaper model"
          + (f", {errors} errors" if errors else "") + ".")
    print("Now run:  modelpilot digest --days 1")


if __name__ == "__main__":
    main()
