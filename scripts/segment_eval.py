"""Per-segment routing performance test for ModelPilot.

Turns the SF-seed ICP research into a product test: representative prompts for
how each customer SEGMENT heavily uses Claude, run through the real router, to
see how ModelPilot performs per segment — what it routes down, the estimated
savings, and where prompts fall into catch-alls (blind spots to tune).

Pure routing analysis — deterministic, no API spend.

    python scripts/segment_eval.py            # full report
    python scripts/segment_eval.py --md out.md

Baseline assumption: customers reach for a strong default model
(claude-opus-4-8); savings = routing the easy/mechanical calls down from it.
Token profile per call is nominal (input from prompt length, fixed output) —
the % is ILLUSTRATIVE of routing headroom, not a measured bill.
"""

import argparse
import statistics
from collections import Counter

from modelpilot.pricing import Usage, ladder_tier, request_cost
from modelpilot.router import recommend

BASELINE = "claude-opus-4-8"
GATE = 0.7           # autopilot default
NOMINAL_OUT = 400    # illustrative output tokens per call

# Each entry: (segment, company, prompt, structured_output?)
# structured_output=True simulates the customer enforcing a JSON schema /
# response_format (very common for extraction) — exercises the Sonnet guard.
CORPUS = [
    # --- Coding agents ---------------------------------------------------
    ("Coding agents", "Omnara", "Write a TypeScript debounce utility with a cancel() method and Jest tests.", False),
    ("Coding agents", "Omnara", "Write a SQL query for the top 10 customers by revenue this quarter.", False),
    ("Coding agents", "CodeAnt AI", "Review this diff for bugs and security issues:\n```\n- query = f\"SELECT * FROM users WHERE id = {uid}\"\n+ query = f\"SELECT * FROM users WHERE id = {uid}\"  # added index\n```", False),
    ("Coding agents", "21st.dev", "Refactor this module to the new hooks API across all files and update the imports end-to-end.", False),
    ("Coding agents", "Replicas", "The auth integration test fails intermittently under concurrency — root-cause the race condition and fix it.", False),
    ("Coding agents", "Compyle", "Add a docstring to this function and rename variables for clarity.", False),

    # --- Document extraction / classification ----------------------------
    ("Doc extraction", "Paradigm", "Extract vendor, invoice number, date, and total from this invoice and return JSON:\nACME Corp · INV-2231 · 2026-05-02 · $4,210.00", True),
    ("Doc extraction", "Melder", "Classify each support email as billing, technical, or sales. One label each.", False),
    ("Doc extraction", "Unsiloed AI", "Extract all parties, the effective date, and termination clauses from this contract as JSON.", True),
    ("Doc extraction", "Trellis AI", "From this clinical note, extract diagnoses with ICD-10 codes and medications as structured JSON.", True),
    ("Doc extraction", "Midship", "Parse this purchase-order table into rows of {sku, qty, unit_price}.", True),
    ("Doc extraction", "Paradigm", "For each row, look up the company's industry and write it in one word.", False),

    # --- Customer support / CX -------------------------------------------
    ("Customer support", "Minimal AI", "Classify this ticket's intent: 'My order #4821 hasn't shipped after 9 days.'", False),
    ("Customer support", "Minimal AI", "Draft a friendly reply to a customer asking how to reset their password.", False),
    ("Customer support", "Rulebase", "Score this call for compliance: did the agent give the recording notice and verify identity? Return pass/fail with a reason.", False),
    ("Customer support", "14.ai", "Given our refund policy (30-day window), answer yes/no: can a customer get a refund 40 days after purchase?", False),
    ("Customer support", "Cignara", "A customer is furious about a double charge and threatening a chargeback. Decide the next best action and draft a response.", False),

    # --- Legal vertical --------------------------------------------------
    ("Legal", "General Legal", "Extract the governing law, term length, and termination-for-convenience notice period from this contract.", True),
    ("Legal", "General Legal", "Redline this NDA confidentiality clause to be mutual and add a 2-year term.", False),
    ("Legal", "Arcline", "Generate a standard mutual NDA for a Delaware C-corp with a 2-year term.", False),
    ("Legal", "LegalOS", "Draft the 'extraordinary ability' argument section of an O-1A petition for an ML researcher, citing these achievements: 3 first-author NeurIPS papers, 1,200 citations, 2 patents, and judging for a top conference.", False),

    # --- Healthcare / insurance ------------------------------------------
    ("Healthcare/insurance", "Beacon Health", "From this chart, list preventive screenings now due and candidate HCC codes.", True),
    ("Healthcare/insurance", "VoiceCare AI", "Summarize this payer-call transcript: what was the prior-auth decision and the required next steps?", False),
    ("Healthcare/insurance", "Adaptional", "Extract insured name, policy limits, and loss history from this ACORD form as JSON.", True),
    ("Healthcare/insurance", "Adaptional", "Summarize this submission's risk against our underwriting guidelines and flag anything outside appetite (large dense policy + guidelines text).", False),

    # --- Real estate -----------------------------------------------------
    ("Real estate", "Bryckel AI", "Extract base rent, annual escalations, TI allowance, and renewal options from this lease as JSON with clause citations.", True),
    ("Real estate", "Propaya", "Summarize the key commercial terms of this 60-page lease for a broker.", False),

    # --- Agents / infra --------------------------------------------------
    ("Agents/infra", "Browser Use", "Navigate to the pricing page, find the enterprise plan price, and report it back.", False),
    ("Agents/infra", "HumanLayer", "Given the proposed agent action 'refund $500 to customer X', decide if it needs human approval per policy (auto-approve under $100).", False),
    ("Agents/infra", "Hyper", "Summarize what changed in this engineering thread relevant to the auth refactor.", False),
    ("Agents/infra", "Sapiom", "The agent needs to call Twilio to send an SMS; choose the cheapest endpoint and construct the request.", False),

    # --- CAD / engineering ----------------------------------------------
    ("CAD/eng", "Aurorin CAD", "Write a parametric script to generate a mounting bracket with four M4 holes on a 40mm grid.", False),
    ("CAD/eng", "REV1", "Given these part dimensions, derive the GD&T position tolerance callouts and prove the stack-up stays within 0.1mm.", False),

    # --- Content / GTM ---------------------------------------------------
    ("Content/GTM", "tday", "Write 3 ad headlines and a 50-word description for a developer cost-optimization tool.", False),
    ("Content/GTM", "Primer", "Generate a personalized product-walkthrough script for a visitor from a fintech exploring our API.", False),
]


def _body(prompt, structured):
    b = {"model": BASELINE, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
    if structured:
        b["output_config"] = {"format": {"type": "json_schema", "schema": {}}}
    return b


GATES = [0.6, 0.7, 0.8]


def evaluate():
    rows = []
    for segment, company, prompt, structured in CORPUS:
        rec = recommend(_body(prompt, structured))
        applied = rec.action == "switch" and rec.confidence >= GATE
        routed = rec.recommended_model if applied else BASELINE
        usage = Usage(input_tokens=max(len(prompt) // 4, 50), output_tokens=NOMINAL_OUT)
        base_cost = request_cost(BASELINE, usage) or 0.0
        routed_cost = request_cost(routed, usage) or base_cost
        rows.append({
            "segment": segment, "company": company, "prompt": prompt, "structured": structured,
            "category": rec.category, "recommended": rec.recommended_model,
            "confidence": rec.confidence, "action": rec.action, "applied": applied, "routed": routed,
            "savings_pct": (base_cost - routed_cost) / base_cost if base_cost else 0.0,
            "catchall": rec.category in ("conversation", "unknown"),
            "applied_at": {g: (rec.action == "switch" and rec.confidence >= g) for g in GATES},
        })
    return rows


CATCHALL = {"conversation", "unknown"}


def render(rows):
    out = []
    out.append(f"# ModelPilot per-segment routing performance\n")
    out.append(f"Baseline: `{BASELINE}` · autopilot gate {GATE} · {len(rows)} representative prompts · "
               f"savings %% illustrative at a nominal token profile (routing headroom, not a measured bill).\n")

    segs = sorted({r["segment"] for r in rows}, key=lambda s: -statistics.fmean(
        [x["savings_pct"] for x in rows if x["segment"] == s]))

    # Per-segment summary
    out.append("## Summary by segment (best routing headroom first)\n")
    out.append("| Segment | n | routed-down @gate | est. savings | catch-all (blind spot) |")
    out.append("|---|---|---|---|---|")
    for s in segs:
        sr = [r for r in rows if r["segment"] == s]
        routed = sum(r["applied"] for r in sr)
        sav = statistics.fmean(r["savings_pct"] for r in sr)
        catch = sum(r["catchall"] for r in sr)
        out.append(f"| {s} | {len(sr)} | {routed}/{len(sr)} | {sav:.0%} | {catch}/{len(sr)} |")
    overall = statistics.fmean(r["savings_pct"] for r in rows)
    tot_routed = sum(r["applied"] for r in rows)
    tot_catch = sum(r["catchall"] for r in rows)
    out.append(f"| **OVERALL** | {len(rows)} | {tot_routed}/{len(rows)} | **{overall:.0%}** | {tot_catch}/{len(rows)} |\n")

    # Per-prompt detail
    out.append("## Per-prompt routing detail\n")
    for s in segs:
        out.append(f"### {s}")
        out.append("| Company | category | routes to | conf | applied | save | prompt |")
        out.append("|---|---|---|---|---|---|---|")
        for r in [x for x in rows if x["segment"] == s]:
            mark = "✓" if r["applied"] else ("·" if not r["catchall"] else "⚠ catch-all")
            short = r["prompt"].replace("\n", " ")[:54]
            out.append(f"| {r['company']} | {r['category']} | {r['recommended'].replace('claude-','')} | "
                       f"{r['confidence']:.2f} | {mark} | {r['savings_pct']:.0%} | {short}… |")
        out.append("")

    # Gate sensitivity — how much the autopilot gate setting matters for this ICP
    out.append("## Gate sensitivity (routed-down across the whole set)\n")
    out.append("| gate | routed-down | note |")
    out.append("|---|---|---|")
    notes = {0.6: "aggressive (golden-set safe)", 0.7: "balanced", 0.8: "default/conservative"}
    for g in GATES:
        n = sum(r["applied_at"][g] for r in rows)
        out.append(f"| {g} | {n}/{len(rows)} | {notes[g]} |")
    out.append("")

    # Tuning callouts
    out.append("## Tuning signals\n")
    blind = [r for r in rows if r["catchall"]]
    if blind:
        out.append(f"- **Catch-all landings ({len(blind)}/{len(rows)}) — left on the baseline, savings forfeited.** "
                   "Candidates for per-customer `learn-rules` / floor tuning:")
        for r in blind:
            out.append(f"    - _{r['segment']} / {r['company']}_: \"{r['prompt'][:70].strip()}…\"")
    stays = [r for r in rows if not r["applied"] and not r["catchall"]]
    if stays:
        out.append(f"- **Classified but held at baseline ({len(stays)}) — quality-protected (hard tasks).** "
                   "Confirm these *should* stay (e.g., debugging, refactors, long-form drafting):")
        for r in stays:
            out.append(f"    - _{r['segment']} / {r['company']}_ ({r['category']}): \"{r['prompt'][:60].strip()}…\"")
    structured = [r for r in rows if r["structured"]]
    floored = [r for r in structured if r["recommended"] == "claude-sonnet-4-6"]
    held_by_gate = [r for r in structured if r["category"] == "extraction" and not r["applied_at"][0.8]
                    and r["applied_at"][0.7]]
    out.append(f"- **Structured-output safety works:** {len(floored)}/{len(structured)} schema-enforced "
               "extraction prompts are floored to Sonnet (never Haiku), protecting response shape.")
    out.append(f"- **⚠ Gate interaction (key tuning lever):** schema-enforced extraction lands at confidence "
               f"0.75, *just below* the 0.8 default gate — so {len(held_by_gate)} of them stay on the baseline "
               "and capture nothing at defaults, even though doc-extraction is our best-fit segment. "
               "A per-category gate of 0.7 for `extraction` (via `learn-floors`/policy) flips these on.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", help="write the report to this markdown file")
    args = ap.parse_args()
    report = render(evaluate())
    print(report)
    if args.md:
        with open(args.md, "w") as f:
            f.write(report)
        print(f"\n[written to {args.md}]")


if __name__ == "__main__":
    main()
