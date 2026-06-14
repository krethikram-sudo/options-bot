"""Continuous, per-customer tuning — the product gets better the more it is
used. It reads THIS deployment's own traffic and writes a policy that adjusts
the per-category confidence gate:

  - a category that has routed at volume with zero escalations and zero negative
    feedback is proven safe *for this customer*, so we lower its gate to capture
    more savings;
  - a category that has caused escalations or negative feedback is raised toward
    "blocked", so we stop routing the thing that hurt quality here.

The gateway loads the result via MODELPILOT_POLICY and applies it in `decide`.
Re-run as traffic accumulates; the policy converges on the customer's mix.

    modelpilot tune --db modelpilot.db --out policy.json
    # then: MODELPILOT_POLICY=policy.json modelpilot gateway --mode autopilot
"""
import argparse
import json
import time

from .ledger import Ledger

DEFAULT_GATE = 0.7       # global autopilot gate (golden-set false-downgrade 0% at >=0.6)
AGGRESSIVE_GATE = 0.6    # proven-safe categories: capture more
BLOCK_GATE = 0.99        # categories that hurt quality here: effectively off
MIN_APPLIED = 20         # need this many clean routes before we trust loosening
INCIDENT_RATE = 0.02     # >2% escalation/negative rate -> tighten


def policy_from_quality(rows: list[dict], default_gate: float = DEFAULT_GATE,
                        loosen_to: float = AGGRESSIVE_GATE, block_to: float = BLOCK_GATE,
                        min_applied: int = MIN_APPLIED, incident_rate: float = INCIDENT_RATE) -> dict:
    """Turn per-category outcomes into a gate policy. Pure — shared by the manual
    `modelpilot tune` command and the gateway's live auto-tuner.

      - a category with >=2 incidents above the incident-rate threshold is blocked
        (gate raised toward 1.0) — quality protection always wins;
      - a category with enough clean routes and zero incidents is loosened to
        capture more — only ever for traffic that has proven safe HERE.
    """
    gates, notes = {}, []
    for r in rows:
        cat, n = r["category"], r["n_applied"]
        incidents = r["n_escalation"] + r["n_negative"]
        rate = incidents / n if n else 0.0
        if incidents >= 2 and rate > incident_rate:
            gates[cat] = block_to
            notes.append(f"{cat}: {incidents} incidents in {n} routes ({rate:.0%}) "
                         f"-> gate {block_to} (stop routing here)")
        elif incidents == 0 and n >= min_applied and default_gate > loosen_to:
            gates[cat] = loosen_to
            notes.append(f"{cat}: {n} clean routes, 0 incidents "
                         f"-> gate {loosen_to} (capture more)")
    return {"category_gates": gates, "notes": notes}


def build_policy(db_path: str, since_days: float = 30.0,
                 default_gate: float = DEFAULT_GATE) -> dict:
    ledger = Ledger(db_path)
    try:
        since = time.time() - since_days * 86_400 if since_days else 0.0
        rows = ledger.category_quality(since)
    finally:
        ledger.close()

    learned = policy_from_quality(rows, default_gate=default_gate)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "since_days": since_days,
        "default_gate": default_gate,
        "category_gates": learned["category_gates"],
        "notes": learned["notes"],
    }


def main():
    parser = argparse.ArgumentParser(description="Per-customer continuous tuning")
    parser.add_argument("--db", default="modelpilot.db")
    parser.add_argument("--days", type=float, default=30.0, help="traffic window (0 = all time)")
    parser.add_argument("--default-gate", type=float, default=DEFAULT_GATE)
    parser.add_argument("--out", default="policy.json")
    args = parser.parse_args()

    policy = build_policy(args.db, args.days, args.default_gate)
    with open(args.out, "w") as f:
        json.dump(policy, f, indent=2)

    if policy["notes"]:
        print("Learned from your traffic:")
        for note in policy["notes"]:
            print(f"  - {note}")
    else:
        print("Not enough traffic yet to adjust any category — keep routing and re-run.")
    print(f"\nPolicy written to {args.out}. Apply it:")
    print(f"  MODELPILOT_POLICY={args.out} modelpilot gateway --mode autopilot")


if __name__ == "__main__":
    main()
