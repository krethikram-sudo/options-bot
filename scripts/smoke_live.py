#!/usr/bin/env python3
"""LIVE measured-savings mini control-arm. For a representative ICP sample:
  - get the real routing decision (router.recommend, gate 0.60),
  - call the BASELINE model (Opus) for real -> real tokens/cost,
  - if routed, call the CHEAPER model for real -> real tokens/cost,
  - LLM-judge (Opus) whether the cheaper answer is non-inferior for the task.
Reports MEASURED savings (real tokens, not estimates) + a quality-preserved rate.
Uses the vendor ANTHROPIC_API_KEY for internal eval. Frugal: small max_tokens."""
import json
import anthropic
from modelpilot import router
from modelpilot.pricing import request_cost, Usage

OPUS = "claude-opus-4-8"
GATE = 0.60
c = anthropic.Anthropic()

_CONTRACT = ("This Master Services Agreement governs services between the parties. "
             "Payment is net-30. Either party may terminate with 30 days written notice. "
             "The cap is the fees paid in the prior 12 months. Ownership of materials "
             "created remains with the disclosing party. ") * 110  # ~6.9k tokens (> long-summary floor)

# (label, system, prompt, max_tokens) — representative spread incl. the fixed long-summary case
SAMPLE = [
    ("Intent classification", "You label support messages.",
     "Classify into one of billing/bug/cancellation/other: 'My card was charged twice, I want a refund.' Answer with one word.", 20),
    ("Field extraction", "You extract structured data.",
     "Extract vendor, invoice_number, total from: 'Invoice INV-2025-418 from Acme Cloud, total $4,210.55, due 2025-07-15.' Return JSON.", 120),
    ("Short Q&A", "You are a concise support assistant.",
     "How do I reset my password on the mobile app? One short paragraph.", 150),
    ("Translation", "You translate text.",
     "Translate to English: 'No puedo iniciar sesion despues de actualizar la app, me sale un error.'", 80),
    ("Rewrite reply", "You write support replies.",
     "Rewrite warmer and more concise: 'Your issue is resolved. Closing the ticket.'", 100),
    ("Summarize contract (LONG)", "You summarize documents.",
     "Summarize this master services agreement: term, payment, termination, liability, IP. One short paragraph.\n\n" + _CONTRACT, 300),
    ("Debugging (HARD - should stay)", "You are a senior engineer.",
     "Our ingestion worker intermittently drops messages under load — root-cause the likely race condition and propose a fix.", 400),
    ("Strategy (HARD - should stay)", "You are a strategy advisor.",
     "We're weighing the trade-offs of hedging FX exposure with forwards vs options. Recommend an approach with reasoning.", 400),
]

def call(model, system, prompt, max_tokens):
    r = c.messages.create(model=model, max_tokens=max_tokens, system=system,
                          messages=[{"role": "user", "content": prompt}])
    txt = "".join(b.text for b in r.content if b.type == "text")
    return txt, Usage(input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens)

def judge(task, ref, cand):
    q = (f"Grade whether a cheaper model's answer is non-inferior (acceptable for "
         f"production) vs a reference, for this task.\n\nTASK:\n{task[:1500]}\n\n"
         f"REFERENCE (premium):\n{ref[:1500]}\n\nCANDIDATE (cheaper):\n{cand[:1500]}\n\n"
         f'Reply ONLY JSON: {{"acceptable": true|false, "why": "<=15 words"}}')
    txt, _ = call(OPUS, "You are a strict, fair evaluator.", q, 120)
    try:
        s = txt[txt.index("{"):txt.rindex("}")+1]
        return json.loads(s)
    except Exception:
        return {"acceptable": None, "why": "judge parse error: " + txt[:60]}

print("="*100)
print("LIVE MEASURED-SAVINGS MINI CONTROL-ARM — real Claude calls, real tokens (gate %.2f)" % GATE)
print("="*100)
print(f"{'task':<34} {'category':<18} {'decision':<16} {'base$':>9} {'routed$':>9} {'save%':>6} {'quality':>9}")
print("-"*100)

tot_base = tot_routed = 0.0
kept = switches = 0
for label, system, prompt, mx in SAMPLE:
    body = {"model": OPUS, "max_tokens": mx, "system": system,
            "messages": [{"role": "user", "content": prompt}]}
    rec = router.recommend(body)
    switch = rec.action == "switch" and rec.confidence >= GATE
    routed_model = rec.recommended_model if switch else OPUS

    base_txt, base_u = call(OPUS, system, prompt, mx)
    base_cost = request_cost(OPUS, base_u) or 0.0
    if switch:
        routed_txt, routed_u = call(routed_model, system, prompt, mx)
        routed_cost = request_cost(routed_model, routed_u) or 0.0
        verdict = judge(prompt, base_txt, routed_txt)
        q = {True: "kept ✓", False: "DEGRADED", None: "?"}[verdict.get("acceptable")]
        switches += 1
        if verdict.get("acceptable"): kept += 1
    else:
        routed_cost = base_cost; q = "(stayed)"

    tot_base += base_cost; tot_routed += routed_cost
    savepct = (base_cost - routed_cost)/base_cost*100 if base_cost else 0
    dec = "stay" if not switch else "→"+routed_model.replace("claude-","")
    print(f"{label[:34]:<34} {rec.category:<18} {dec:<16} "
          f"${base_cost*100:>7.4f}c ${routed_cost*100:>7.4f}c {savepct:>5.0f}% {q:>9}")

print("-"*100)
blended = (tot_base - tot_routed)/tot_base*100 if tot_base else 0
print(f"MEASURED on this real sample: baseline ${tot_base:.5f}  routed ${tot_routed:.5f}  "
      f"saved {blended:.1f}% of bill")
print(f"Quality preserved on switches: {kept}/{switches} judged non-inferior by Opus")
print("(c = cents/request; real token counts from the API, not estimates.)")
