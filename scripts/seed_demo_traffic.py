#!/usr/bin/env python3
"""Replay a small, realistic mixed-difficulty workload through the ModelPilot
gateway so the digest/dashboard show a representative savings number.

It simulates a customer who defaults *everything* to one expensive model
(--baseline, default Opus) — exactly the over-provisioning ModelPilot exists to
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

# A representative mix: ~half cheap/mechanical (routable to Haiku), some mid
# (Sonnet), some genuinely hard (stays on the top model). This spread is what
# makes the savings number honest rather than rosy.
PROMPTS = [
    # --- cheap / mechanical: should route down to Haiku ---
    "Classify the sentiment as positive, negative, or neutral: 'the app keeps crashing but support was kind'.",
    "Extract the dates from: 'Invoice issued 2024-03-02, due 2024-04-01, paid 2024-03-28.'",
    "Translate to French: 'Your order has shipped and will arrive Tuesday.'",
    "What is the boiling point of water at sea level in Celsius?",
    "Turn these into a numbered list: buy milk, call dentist, submit report.",
    "What does HTTP status code 404 mean?",
    "Pull out the email and phone number from: 'Reach me at sam@acme.co or 555-0142.'",
    "Is this likely spam? 'Congratulations, you won a $1000 gift card, click here now.'",
    "Summarize in one sentence: 'Q3 revenue rose 12% on enterprise demand, while support costs fell after automation.'",
    "Translate to Spanish: 'The meeting has been moved to 3pm.'",
    "Give the past tense of: run, swim, bring, think.",
    # --- mid: should hold at Sonnet (incl. audience-constrained rewrite) ---
    "Rewrite this for a customer-facing status page: 'db fell over, oncall paged, fixed in 20m'.",
    "Write a Python function that returns True if a string is a palindrome.",
    "Make this more concise and professional: 'hey just wanted to check in and see if maybe you had a sec to look at the thing'.",
    "Summarize the key decisions from these notes: 'Agreed to ship beta Friday, postpone billing redesign, hire one SRE.'",
    # --- hard: should stay on the top model ---
    "Why does this recurse infinitely, and how do you fix it? def f(n): return f(n-1) if n else f(0)",
    "A bat and a ball cost $1.10 total; the bat costs $1.00 more than the ball. How much is the ball?",
    "Design a caching strategy for a read-heavy API at 100M requests/day with strict read-after-write consistency.",
    "Implement a thread-safe LRU cache in Python with O(1) get and put.",
    "This SQL deadlocks under load; give the likely causes and concrete fixes: UPDATE accounts SET bal=bal-1 WHERE id=?; UPDATE accounts SET bal=bal+1 WHERE id=?;",
    "Compare event sourcing vs CRUD for an audit-heavy fintech ledger and recommend one with reasoning.",
    "Prove that the sum of the first n odd numbers equals n squared.",
]


def main():
    base = os.environ.get("ANTHROPIC_BASE_URL", "http://127.0.0.1:8410").rstrip("/")
    key = os.environ.get("ANTHROPIC_API_KEY")
    baseline = sys.argv[1] if len(sys.argv) > 1 else "claude-opus-4-8"
    if not key:
        sys.exit("Set ANTHROPIC_API_KEY (the gateway forwards it upstream).")
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
