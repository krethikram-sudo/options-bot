#!/usr/bin/env python3
"""Smoke test: drive realistic ICP customer traffic through the REAL routing
decision (modelpilot.router.recommend) + REAL pricing math. Decisions come from
production code; the $ use explicit, stated per-request token volumes (labeled
illustrative, since true baseline volumes are only known when measured live)."""
from modelpilot import router
from modelpilot.pricing import request_cost, Usage, PRICES, CAPABILITY_LADDER, ladder_tier

OPUS = "claude-opus-4-8"   # what a cautious ICP customer defaults everything to
HARD = {"codegen_complex", "debugging", "math_logic", "agentic", "analysis_strategy"}

def body(prompt, system="You are a helpful assistant.", model=OPUS, max_tokens=1024,
         tools=None, output_config=None, extra_msgs=None):
    msgs = list(extra_msgs or []) + [{"role": "user", "content": prompt}]
    b = {"model": model, "system": system, "messages": msgs, "max_tokens": max_tokens}
    if tools: b["tools"] = tools
    if output_config: b["output_config"] = output_config
    return b

# (persona, short label, body, (input_tokens, output_tokens) for $ est, expected-ish)
B = []
def add(persona, label, b, intok, outtok):
    B.append((persona, label, b, intok, outtok))

# ---------- Persona A: Support / CX automation company (Chatbase-like) ----------
P = "Support/CX"
add(P, "Intent classification",
    body("Classify this customer message into exactly one of: billing, bug, "
         "feature_request, cancellation, other.\n\n'Hey my card got charged twice "
         "this month and I want a refund.'"), 220, 8)
add(P, "Ticket sentiment",
    body("What is the sentiment (positive/neutral/negative) of this review? "
         "'Support took 4 days to reply and never fixed my issue.'"), 90, 6)
add(P, "Summarize support thread",
    body("Summarize the key issue and the resolution in this 38-message support "
         "thread in 3 bullet points."), 4200, 180)
add(P, "Draft reply (rewrite)",
    body("Rewrite this draft reply to be warmer and more concise:\n'Your issue is "
         "resolved. Closing the ticket.'"), 120, 90)
add(P, "FAQ short answer",
    body("Answer briefly: how do I reset my password on the mobile app?"), 60, 70)
add(P, "Translate ticket",
    body("Translate this support ticket to English:\n'No puedo iniciar sesion "
         "despues de actualizar la app, me sale un error 500.'"), 80, 60)
add(P, "Extract fields (structured output)",
    body("Extract order_id, issue_type, and refund_requested (bool) as JSON.\n"
         "'Order A-3391 arrived broken, please refund.'",
         output_config={"format": {"type": "json_schema", "schema": {}}}), 140, 60)
add(P, "Churn analysis (HARD)",
    body("Analyze our last quarter of churned-account notes and recommend the top 3 "
         "retention strategy changes, with trade-offs and a rollout sequence."), 5200, 900)
add(P, "Debug our pipeline (HARD)",
    body("Our ingestion worker intermittently drops messages under load. Here's the "
         "consumer loop and the broker config; root-cause the race condition and "
         "propose a fix.\n```python\nwhile True:\n    msg = q.get()\n    ...\n```"), 1400, 700)

# ---------- Persona B: Legal / contract-ops ----------
P = "Legal/ops"
add(P, "Clause extraction",
    body("Extract the governing law, termination notice period, and liability cap "
         "from this contract section."), 1800, 120)
add(P, "Classify clause risk",
    body("Label this indemnification clause as low/medium/high risk for the vendor."), 600, 10)
add(P, "Summarize contract (long)",
    body("Summarize this 22-page master services agreement: parties, term, payment, "
         "termination, liability, IP. One paragraph each."), 14000, 700)
add(P, "Plain-language rewrite",
    body("Rewrite this clause in plain English for a non-lawyer:\n'The party of the "
         "first part shall indemnify and hold harmless...'"), 260, 160)
add(P, "Legal strategy (HARD)",
    body("Given these three conflicting precedents, what's the strongest argument "
         "for our position in this jurisdiction, and what's the biggest weakness "
         "opposing counsel will exploit? Reason carefully."), 3600, 1200)

# ---------- Persona C: Fintech / back-office doc processing ----------
P = "Fintech/ops"
add(P, "Invoice field extraction",
    body("Extract vendor, invoice_number, total_amount, due_date from this invoice text."), 900, 90)
add(P, "Transaction classification",
    body("Categorize this transaction into one of our 12 expense categories: "
         "'AWS EMEA SARL 4,210.55 USD'."), 70, 8)
add(P, "KYC doc summary",
    body("Summarize this customer onboarding document into a 4-line risk profile."), 2600, 140)
add(P, "Write a SQL query (simple code)",
    body("Write a single SQL query: total revenue by month for 2025 from a "
         "`payments(amount, created_at, status)` table where status='succeeded'."), 110, 130)
add(P, "Fraud pattern analysis (HARD)",
    body("Here are 50k flagged transactions' aggregate stats. Derive the likely "
         "fraud ring structure and quantify expected loss under two scenarios. "
         "Show the math."), 3000, 1100)
add(P, "Tool-using agent step",
    body("Look up the customer's last 3 payments and decide whether to auto-approve "
         "the refund.",
         tools=[{"name": "get_payments", "description": "x",
                 "input_schema": {"type": "object"}}]), 300, 120)

# ---------- cross-cutting edge cases ----------
P = "Edge cases"
add(P, "Follow-up in a hard coding session",
    body("now make it thread-safe",
         extra_msgs=[
             {"role": "user", "content": "Refactor this multi-file payment "
              "reconciliation service to fix the race condition in the ledger writer."},
             {"role": "assistant", "content": "Here's the refactor across "
              "ledger.py and worker.py ... [long code]"}]), 2500, 600)
add(P, "Already on Haiku (no headroom)",
    body("Classify: spam or not? 'WIN A FREE IPHONE NOW'", model="claude-haiku-4-5"), 40, 6)

# ---------------- run ----------------
print("="*108)
print("MODELPILOT SMOKE TEST — real router.recommend() decisions on ICP traffic; $ at list price, stated volumes")
print("="*108)
hdr = f"{'persona':<12} {'task':<34} {'category':<20} {'decision':<22} {'conf':>4}  {'base$':>8} {'routed$':>8} {'save$':>8}"
print(hdr); print("-"*108)

tot_base = tot_routed = 0.0
switched = 0
protection_violations = []
guard_checks = []
gated_out = []
rows = []
GATE = 0.60  # production confidence gate (matches goldenset recommended gate)
for persona, label, b, intok, outtok in B:
    rec = router.recommend(b)
    # Production applies a confidence gate: low-confidence switches are held back.
    if rec.action == "switch" and rec.confidence < GATE:
        gated_out.append((label, rec.category, rec.recommended_model, rec.confidence))
        routed_model = b["model"]; action = "stay"
    else:
        routed_model = rec.recommended_model; action = rec.action
    base_model = b["model"]
    u = Usage(input_tokens=intok, output_tokens=outtok)
    base_cost = request_cost(base_model, u) or 0.0
    routed_cost = request_cost(routed_model, u) or 0.0
    save = base_cost - routed_cost
    tot_base += base_cost; tot_routed += routed_cost
    dec = "stay" if action == "stay" else f"switch→{routed_model.replace('claude-','')}"
    if action == "switch": switched += 1
    if rec.category in HARD and ladder_tier(routed_model) < ladder_tier(OPUS):
        protection_violations.append((label, rec.category, routed_model))
    if (b.get("tools") or b.get("output_config")) and action == "switch":
        guard_checks.append((label, routed_model, "OK" if "sonnet" in routed_model else "FAIL<sonnet"))
    rows.append((persona, label, rec.category, dec, rec.confidence, base_cost, routed_cost, save))

for persona, label, cat, dec, conf, bc, rc, sv in rows:
    print(f"{persona:<12} {label[:34]:<34} {cat:<20} {dec:<22} {conf:>4.2f}  "
          f"{bc*1000:>7.3f}m {rc*1000:>7.3f}m {sv*1000:>7.3f}m")
print("-"*108)
print("($ shown in milli-dollars per request, i.e. 'm' = $/1000, at list price for the stated token volumes)")

n = len(B)
blended = (tot_base - tot_routed) / tot_base * 100 if tot_base else 0
print(f"\nRequests: {n}   |   switched (routed cheaper): {switched} ({switched/n*100:.0f}%)   |   "
      f"stayed/protected: {n-switched}")
print(f"Per-basket cost @ list: baseline ${tot_base:.5f}  routed ${tot_routed:.5f}  "
      f"saved ${tot_base-tot_routed:.5f}  ({blended:.1f}% of bill)")

# project to a realistic ICP monthly bill, holding this traffic mix
for monthly in (10_000, 30_000):
    saved = monthly * blended/100
    fee = saved * 0.20
    print(f"  If this mix were a ${monthly:,}/mo Opus bill → save ~${saved:,.0f}/mo, "
          f"MP fee (20%) ~${fee:,.0f}, customer nets ~${saved-fee:,.0f}/mo")

print(f"\nGATED OUT (low-confidence switches held back at gate {GATE} → stayed on Opus): {len(gated_out)}")
for label, cat, model, conf in gated_out:
    print(f"  · {label}  (read as {cat}→{model.replace('claude-','')}, conf {conf:.2f}) — safely kept on Opus")

print("\nSAFETY AUDIT")
print(f"  Hard-task protection (no codegen_complex/debugging/math/agentic/analysis routed below Opus): "
      f"{'PASS ✓' if not protection_violations else 'FAIL ✗ '+str(protection_violations)}")
print(f"  Tool/structured-output guard (floored at Sonnet, never Haiku): "
      f"{guard_checks if guard_checks else 'no switchable guarded cases'}")
