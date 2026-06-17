#!/usr/bin/env python3
"""Append realistic LONG-document summarization rows to the golden set.

These cover the failure mode found in the smoke test: a "summarize…" instruction
over a long/dense source must floor at Sonnet (summarization_long), not Haiku.
Each prompt is a genuinely long (>6k token) but mundane document so the label is
unambiguous. Honest provenance: label_source = synthetic_heuristic. Idempotent
(skips ids already present)."""
import json, os

LABELS = "modelpilot/goldenset_data/labels.jsonl"

def long_doc(lines, reps):
    return "\n".join(f"[{i:03d}] {lines[i % len(lines)]}" for i in range(len(lines) * reps))

SUPPORT = [
    "Customer: I'd like to switch my plan from monthly to annual.",
    "Agent: happy to help — annual saves about 15% versus monthly.",
    "Customer: does the new price apply now or on my next renewal?",
    "Agent: it applies on your next renewal date, the 14th.",
    "Customer: can I also update the card you have on file?",
    "Agent: sure — it's under Settings, then Payment methods.",
    "Customer: the page just keeps spinning on my phone.",
    "Agent: try the desktop site for now, or I can update it for you.",
    "Customer: please move me to the annual plan.",
    "Agent: all set — you'll see it on your next invoice.",
    "Customer: when does the receipt arrive?",
    "Agent: it emails right after the renewal goes through.",
]
STANDUP = [
    "Alex: yesterday I finished the onboarding copy and the welcome email.",
    "Priya: I reviewed the new pricing page and left a few wording notes.",
    "Sam: the mobile layout looks good now on small screens.",
    "Alex: today I'll start on the settings page and the profile form.",
    "Priya: I'm meeting the design team about the dashboard icons at 2pm.",
    "Sam: I'll pair with Alex on the form validation this afternoon.",
    "Jordan: reminder that the customer call is moved to Thursday 11am.",
    "Priya: no blockers on my side, just waiting on the copy review.",
    "Sam: one small ask — can we get the updated logo assets?",
    "Alex: I'll drop the logo files in the shared folder after standup.",
    "Jordan: great, let's keep the demo build ready for Friday.",
    "Priya: sounds good, I'll update the board with today's tasks.",
]
FAQ = [
    "Q: How do I reset my password? A: Use 'Forgot password' on the login page.",
    "Q: Can I add teammates? A: Yes, invite them from Settings, Members.",
    "Q: How is billing calculated? A: Monthly, based on your selected plan.",
    "Q: Do you offer annual plans? A: Yes, annual saves about 15%.",
    "Q: How do I cancel? A: Settings, Billing, then Cancel plan.",
    "Q: Where are my invoices? A: Settings, Billing, Invoices.",
    "Q: Can I change my email? A: Yes, under Settings, Profile.",
    "Q: Is there a mobile app? A: Yes, on iOS and Android.",
    "Q: How do I export my data? A: Settings, Data, Export.",
    "Q: What payment methods are supported? A: Major cards and PayPal.",
    "Q: How do I contact support? A: Use the in-app chat or email us.",
    "Q: Do you have a free trial? A: Yes, 7 days, no card required.",
]

ROWS = [
    {"id": "ls-00", "category": "summarization_long", "label_model": "claude-sonnet-4-6",
     "label_source": "synthetic_heuristic",
     "prompt": "Summarize the customer's goal and what was resolved in this support "
               "thread, in 3 bullets.\n\n" + long_doc(SUPPORT, 40)},
    {"id": "ls-01", "category": "summarization_long", "label_model": "claude-sonnet-4-6",
     "label_source": "synthetic_heuristic",
     "prompt": "Summarize this multi-day standup log into a short status update: what "
               "shipped, what's in progress, and any blockers.\n\n" + long_doc(STANDUP, 40)},
    {"id": "ls-02", "category": "summarization_long", "label_model": "claude-sonnet-4-6",
     "label_source": "synthetic_heuristic",
     "prompt": "Summarize the main themes of this help-center FAQ document into key "
               "points for a new-user guide.\n\n" + long_doc(FAQ, 40)},
]

existing = set()
if os.path.exists(LABELS):
    with open(LABELS) as f:
        for line in f:
            if line.strip():
                existing.add(json.loads(line).get("id"))

added = 0
with open(LABELS, "a") as f:
    for r in ROWS:
        if r["id"] in existing:
            print("skip (exists):", r["id"]); continue
        # sanity: prompt must clear the long-summary threshold (~6k tokens)
        approx = len(r["prompt"]) // 4
        assert approx >= 6000, f"{r['id']} only ~{approx} tokens"
        f.write(json.dumps(r) + "\n"); added += 1
        print(f"added {r['id']}  (~{approx} tokens)")
print(f"done: {added} rows appended.")
