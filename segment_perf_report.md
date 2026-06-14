# ModelPilot per-segment routing performance

Baseline: `claude-opus-4-8` · autopilot gate 0.7 · 35 representative prompts · savings %% illustrative at a nominal token profile (routing headroom, not a measured bill).

## Summary by segment (best routing headroom first)

| Segment | n | routed-down @gate | est. savings | catch-all (blind spot) |
|---|---|---|---|---|
| Customer support | 5 | 5/5 | 80% | 0/5 |
| Real estate | 2 | 2/2 | 60% | 0/2 |
| Doc extraction | 6 | 6/6 | 53% | 0/6 |
| Healthcare/insurance | 4 | 3/4 | 50% | 1/4 |
| Coding agents | 6 | 1/6 | 13% | 1/6 |
| Legal | 4 | 1/4 | 10% | 3/4 |
| Agents/infra | 4 | 0/4 | 0% | 3/4 |
| CAD/eng | 2 | 0/2 | 0% | 1/2 |
| Content/GTM | 2 | 0/2 | 0% | 2/2 |
| **OVERALL** | 35 | 18/35 | **33%** | 11/35 |

## Per-prompt routing detail

### Customer support
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| Minimal AI | classification | haiku-4-5 | 0.85 | ✓ | 80% | Classify this ticket's intent: 'My order #4821 hasn't … |
| Minimal AI | rewrite_format | haiku-4-5 | 0.85 | ✓ | 80% | Draft a friendly reply to a customer asking how to res… |
| Rulebase | classification | haiku-4-5 | 0.85 | ✓ | 80% | Score this call for compliance: did the agent give the… |
| 14.ai | classification | haiku-4-5 | 0.85 | ✓ | 80% | Given our refund policy (30-day window), answer yes/no… |
| Cignara | rewrite_format | haiku-4-5 | 0.85 | ✓ | 80% | A customer is furious about a double charge and threat… |

### Real estate
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| Bryckel AI | extraction | sonnet-4-6 | 0.75 | ✓ | 40% | Extract base rent, annual escalations, TI allowance, a… |
| Propaya | summarization_short | haiku-4-5 | 0.85 | ✓ | 80% | Summarize the key commercial terms of this 60-page lea… |

### Doc extraction
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| Paradigm | extraction | sonnet-4-6 | 0.75 | ✓ | 40% | Extract vendor, invoice number, date, and total from t… |
| Melder | classification | haiku-4-5 | 0.85 | ✓ | 80% | Classify each support email as billing, technical, or … |
| Unsiloed AI | extraction | sonnet-4-6 | 0.75 | ✓ | 40% | Extract all parties, the effective date, and terminati… |
| Trellis AI | extraction | sonnet-4-6 | 0.75 | ✓ | 40% | From this clinical note, extract diagnoses with ICD-10… |
| Midship | extraction | sonnet-4-6 | 0.75 | ✓ | 40% | Parse this purchase-order table into rows of {sku, qty… |
| Paradigm | classification | haiku-4-5 | 0.85 | ✓ | 80% | For each row, look up the company's industry and write… |

### Healthcare/insurance
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| Beacon Health | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | From this chart, list preventive screenings now due an… |
| VoiceCare AI | summarization_short | haiku-4-5 | 0.85 | ✓ | 80% | Summarize this payer-call transcript: what was the pri… |
| Adaptional | extraction | sonnet-4-6 | 0.75 | ✓ | 40% | Extract insured name, policy limits, and loss history … |
| Adaptional | summarization_short | haiku-4-5 | 0.85 | ✓ | 80% | Summarize this submission's risk against our underwrit… |

### Coding agents
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| Omnara | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Write a TypeScript debounce utility with a cancel() me… |
| Omnara | codegen_simple | haiku-4-5 | 0.85 | ✓ | 80% | Write a SQL query for the top 10 customers by revenue … |
| CodeAnt AI | codegen_simple | haiku-4-5 | 0.55 | · | 0% | Review this diff for bugs and security issues: ``` - q… |
| 21st.dev | codegen_complex | opus-4-8 | 0.80 | · | 0% | Refactor this module to the new hooks API across all f… |
| Replicas | debugging | opus-4-8 | 0.80 | · | 0% | The auth integration test fails intermittently under c… |
| Compyle | codegen_simple | haiku-4-5 | 0.55 | · | 0% | Add a docstring to this function and rename variables … |

### Legal
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| General Legal | extraction | sonnet-4-6 | 0.75 | ✓ | 40% | Extract the governing law, term length, and terminatio… |
| General Legal | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Redline this NDA confidentiality clause to be mutual a… |
| Arcline | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Generate a standard mutual NDA for a Delaware C-corp w… |
| LegalOS | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Draft the 'extraordinary ability' argument section of … |

### Agents/infra
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| Browser Use | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Navigate to the pricing page, find the enterprise plan… |
| HumanLayer | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Given the proposed agent action 'refund $500 to custom… |
| Hyper | codegen_complex | opus-4-8 | 0.80 | · | 0% | Summarize what changed in this engineering thread rele… |
| Sapiom | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | The agent needs to call Twilio to send an SMS; choose … |

### CAD/eng
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| Aurorin CAD | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Write a parametric script to generate a mounting brack… |
| REV1 | math_logic | opus-4-8 | 0.80 | · | 0% | Given these part dimensions, derive the GD&T position … |

### Content/GTM
| Company | category | routes to | conf | applied | save | prompt |
|---|---|---|---|---|---|---|
| tday | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Write 3 ad headlines and a 50-word description for a d… |
| Primer | conversation | sonnet-4-6 | 0.50 | ⚠ catch-all | 0% | Generate a personalized product-walkthrough script for… |

## Gate sensitivity (routed-down across the whole set)

| gate | routed-down | note |
|---|---|---|
| 0.6 | 18/35 | aggressive (golden-set safe) |
| 0.7 | 18/35 | balanced |
| 0.8 | 11/35 | default/conservative |

## Tuning signals

- **Catch-all landings (11/35) — left on the baseline, savings forfeited.** Candidates for per-customer `learn-rules` / floor tuning:
    - _Coding agents / Omnara_: "Write a TypeScript debounce utility with a cancel() method and Jest te…"
    - _Legal / General Legal_: "Redline this NDA confidentiality clause to be mutual and add a 2-year…"
    - _Legal / Arcline_: "Generate a standard mutual NDA for a Delaware C-corp with a 2-year ter…"
    - _Legal / LegalOS_: "Draft the 'extraordinary ability' argument section of an O-1A petition…"
    - _Healthcare/insurance / Beacon Health_: "From this chart, list preventive screenings now due and candidate HCC…"
    - _Agents/infra / Browser Use_: "Navigate to the pricing page, find the enterprise plan price, and repo…"
    - _Agents/infra / HumanLayer_: "Given the proposed agent action 'refund $500 to customer X', decide if…"
    - _Agents/infra / Sapiom_: "The agent needs to call Twilio to send an SMS; choose the cheapest end…"
    - _CAD/eng / Aurorin CAD_: "Write a parametric script to generate a mounting bracket with four M4…"
    - _Content/GTM / tday_: "Write 3 ad headlines and a 50-word description for a developer cost-op…"
    - _Content/GTM / Primer_: "Generate a personalized product-walkthrough script for a visitor from…"
- **Classified but held at baseline (6) — quality-protected (hard tasks).** Confirm these *should* stay (e.g., debugging, refactors, long-form drafting):
    - _Coding agents / CodeAnt AI_ (codegen_simple): "Review this diff for bugs and security issues:
```
- query =…"
    - _Coding agents / 21st.dev_ (codegen_complex): "Refactor this module to the new hooks API across all files a…"
    - _Coding agents / Replicas_ (debugging): "The auth integration test fails intermittently under concurr…"
    - _Coding agents / Compyle_ (codegen_simple): "Add a docstring to this function and rename variables for cl…"
    - _Agents/infra / Hyper_ (codegen_complex): "Summarize what changed in this engineering thread relevant t…"
    - _CAD/eng / REV1_ (math_logic): "Given these part dimensions, derive the GD&T position tolera…"
- **Structured-output safety works:** 8/8 schema-enforced extraction prompts are floored to Sonnet (never Haiku), protecting response shape.
- **⚠ Gate interaction (key tuning lever):** schema-enforced extraction lands at confidence 0.75, *just below* the 0.8 default gate — so 7 of them stay on the baseline and capture nothing at defaults, even though doc-extraction is our best-fit segment. A per-category gate of 0.7 for `extraction` (via `learn-floors`/policy) flips these on.