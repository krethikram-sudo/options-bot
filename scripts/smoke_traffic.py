"""Smoke test: send a handful of real Claude requests through a local ModelPilot
gateway to verify the end-to-end loop (gateway -> hosted brain -> routing ->
savings metered to the console).

Usage (from the repo root, after the gateway is running on :8400):
  export ANTHROPIC_API_KEY=sk-ant-...      # a real Claude key
  python scripts/smoke_traffic.py

It deliberately asks an expensive model (Opus) for trivial tasks, so the router
has room to downgrade to a cheaper model and realize savings.
"""

import os
import sys

try:
    from anthropic import Anthropic
except ImportError:
    sys.exit("Install deps first:  pip install -r modelpilot/requirements.txt")

GATEWAY = os.environ.get("MODELPILOT_GATEWAY_URL", "http://127.0.0.1:8400")
# The real key so it works whether the gateway forwards the client key or injects
# its own; the gateway is what actually talks to Anthropic.
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    sys.exit("Set ANTHROPIC_API_KEY in your environment first.")

client = Anthropic(base_url=GATEWAY, api_key=API_KEY)

PROMPTS = [
    "Classify the sentiment (positive or negative): 'Absolutely loved it.'",
    "What is the capital of France? One word.",
    "Summarize in one word: the meeting ran long and nothing was decided.",
    "Extract the email address from: contact me at jane@example.com please.",
    "Translate 'good morning' to Spanish.",
    "Is 17 a prime number? Answer yes or no.",
    "Give the past tense of the verb 'run'.",
    "What color do you get mixing blue and yellow? One word.",
]


def main() -> int:
    print(f"Sending {len(PROMPTS)} requests through {GATEWAY} ...\n")
    ok = 0
    for i, prompt in enumerate(PROMPTS, 1):
        try:
            msg = client.messages.create(
                model="claude-opus-4-8", max_tokens=40,
                messages=[{"role": "user", "content": prompt}])
            text = "".join(getattr(b, "text", "") for b in msg.content).strip()
            print(f"[{i}/{len(PROMPTS)}] ok: {text[:70]}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(PROMPTS)}] ERROR: {e!r}")
    print(f"\n{ok}/{len(PROMPTS)} succeeded. Give the gateway ~60s to meter, then "
          "check the console Dashboard/Billing for realized savings.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
