"""Starter golden-set corpus, stratified across the task taxonomy.

  python -m modelpilot.goldenset.seed_corpus --out gs/prompts.jsonl

This is corpus v0 — enough to exercise the full pipeline and produce a first
confidence-gate calibration. It deliberately includes trap cases:

  * simple instruction verb over hard content ("summarize" dense legal text)
  * hard-looking phrasing over trivial content ("prove" something one-line)

Real customer traffic should progressively replace it (ROUTER_TUNING_PLAN.md §3).
`expected` enables programmatic grading; everything else goes to the judge.

Prints the heuristic router's predicted mix at the end as a sanity check —
that is NOT ground truth, just what the current router would do.
"""

import argparse
import json
from collections import Counter

_LEGAL = (
    "Section 7.2. Indemnification. Each party (the \"Indemnifying Party\") shall defend, "
    "indemnify and hold harmless the other party from and against any and all third-party "
    "claims arising out of (a) the Indemnifying Party's gross negligence or willful "
    "misconduct, (b) its breach of Section 5 (Confidentiality), or (c) infringement of "
    "intellectual property rights by materials furnished by the Indemnifying Party, except "
    "to the extent such claims result from the other party's modifications thereof or "
    "combination with materials not furnished by the Indemnifying Party. The foregoing "
    "states the Indemnifying Party's entire liability for third-party claims, provided that "
    "nothing herein limits liability for amounts payable under Section 9.3 or claims that "
    "cannot be limited under applicable law. Notwithstanding the foregoing, the aggregate "
    "liability under this Section 7.2 shall not exceed two times the fees paid or payable "
    "in the twelve months preceding the claim, except for clauses (b) and (c), which are "
    "uncapped."
)

_INCIDENT = (
    "Timeline: 09:02 deploy of build 4811 to us-east. 09:14 p95 latency on /checkout rises "
    "from 180ms to 2.4s. 09:21 error rate hits 11% (connection pool exhaustion in payments-svc). "
    "09:25 rollback initiated; 09:31 rollback complete but error rate stays at 9%. 09:40 "
    "engineer notices payments-svc replicas pinned at max connections to the new read replica "
    "provisioned yesterday; replica has wrong instance class. 09:55 traffic shifted to primary, "
    "error rate normal by 10:02. Customer impact: ~38k failed checkouts."
)

_TICKET = (
    "Hi, I was charged $49.99 twice on March 3rd for my Pro subscription (invoice INV-20331 "
    "and INV-20349). I only have one account, registered under maya.chen@example.com. Please "
    "refund the duplicate. Also, while you're at it, the mobile app keeps logging me out — "
    "this started after the last update. Order ref: ORD-77812. My phone is a Pixel 8."
)

CORPUS: list[dict] = [
    # ----- classification (programmatic) -----
    {"category": "classification", "prompt": "Classify the sentiment of this review as positive, negative, or neutral. Answer with one word.\n\n\"Arrived two days early and works exactly as described.\"", "expected": "positive"},
    {"category": "classification", "prompt": "Classify the sentiment as positive, negative, or neutral. One word only.\n\n\"Oh great, another update that breaks everything. Fantastic work as always.\"", "expected": "negative"},
    {"category": "classification", "prompt": "Is this email spam or not spam? Answer 'spam' or 'not spam'.\n\n\"URGENT: Your account will be suspended! Click here within 24 hours to verify your SSN and avoid fees!!!\"", "expected": "spam"},
    {"category": "classification", "prompt": f"Classify this support ticket's primary intent as one of: refund, bug_report, account_access, other. Answer with the label only.\n\n{_TICKET}", "expected": "refund"},
    {"category": "classification", "prompt": "Label the topic of this headline as sports, politics, technology, or entertainment. One word.\n\n\"Chipmaker unveils 2nm process node, claims 30% power reduction\"", "expected": "technology"},
    {"category": "classification", "prompt": "Triage priority for this alert: answer P1, P2, or P3 only.\n\n\"Production database primary unreachable for 4 minutes; failover did not trigger; all writes failing.\"", "expected": "P1"},
    {"category": "classification", "prompt": "Does the following statement express certainty or uncertainty? Answer 'certainty' or 'uncertainty'.\n\n\"The results might suggest some improvement, though it's hard to say definitively.\"", "expected": "uncertainty"},
    {"category": "classification", "prompt": "Classify this code review comment as blocking or non-blocking. One word.\n\n\"nit: prefer f-strings here, but fine either way\"", "expected": "non-blocking"},

    # ----- extraction (programmatic where single-valued) -----
    {"category": "extraction", "prompt": f"Extract the customer's email address from this ticket. Reply with the email only.\n\n{_TICKET}", "expected": "maya.chen@example.com"},
    {"category": "extraction", "prompt": f"Extract the duplicate-charge invoice numbers from this ticket as a comma-separated list.\n\n{_TICKET}", "expected": "INV-20331, INV-20349"},
    {"category": "extraction", "prompt": f"What is the order reference in this ticket? Reply with the reference only.\n\n{_TICKET}", "expected": "ORD-77812"},
    {"category": "extraction", "prompt": f"From the incident timeline, extract the build number that was deployed. Reply with the number only.\n\n{_INCIDENT}", "expected": "4811"},
    {"category": "extraction", "prompt": f"From the incident timeline, how many checkouts failed? Reply with the number only.\n\n{_INCIDENT}", "expected": "38k"},
    {"category": "extraction", "prompt": "Extract all ISO dates from this sentence as a comma-separated list:\n\n\"The contract was signed on 2025-11-04, amended on 2026-01-19, and renews on 2026-11-04.\"", "expected": "2025-11-04, 2026-01-19, 2026-11-04"},
    {"category": "extraction", "prompt": "Pull out the function name being deprecated:\n\n\"DeprecationWarning: `load_config_legacy` is deprecated and will be removed in 3.0; use `load_config` instead.\"", "expected": "load_config_legacy"},
    {"category": "extraction", "prompt": f"Extract these fields from the ticket as JSON with keys amount, currency, product: {_TICKET}", "expected": "49.99"},

    # ----- translation (judge) -----
    {"category": "translation", "prompt": "Translate to Spanish:\n\n\"Your subscription will renew automatically on the 15th. You can cancel anytime from your account settings.\""},
    {"category": "translation", "prompt": "Translate to French, keeping the friendly tone:\n\n\"Thanks for your patience! We've fixed the issue and your dashboard should load normally now.\""},
    {"category": "translation", "prompt": "Translate to German:\n\n\"Please note that refunds are processed within 5 to 7 business days, depending on your bank.\""},
    {"category": "translation", "prompt": "Translate this technical sentence to Japanese:\n\n\"The API rate limit is 100 requests per minute per key; exceeding it returns HTTP 429.\""},
    {"category": "translation", "prompt": f"Translate this legal clause into Portuguese, preserving precise legal meaning:\n\n{_LEGAL}"},

    # ----- short_qa (programmatic where factual) -----
    {"category": "short_qa", "prompt": "What is the capital of Australia? One word.", "expected": "Canberra"},
    {"category": "short_qa", "prompt": "How many bytes are in a kibibyte? Reply with the number only.", "expected": "1024"},
    {"category": "short_qa", "prompt": "What HTTP status code means 'Too Many Requests'? Number only.", "expected": "429"},
    {"category": "short_qa", "prompt": "What does the acronym CTE stand for in SQL? Short answer.", "expected": "common table expression"},
    {"category": "short_qa", "prompt": "Which planet has the shortest day? One word.", "expected": "Jupiter"},
    {"category": "short_qa", "prompt": "What year was the original Bretton Woods agreement signed? Year only.", "expected": "1944"},

    # ----- summarization_short (judge) -----
    {"category": "summarization_short", "prompt": f"Summarize this incident in two sentences for a status page (no internal details):\n\n{_INCIDENT}"},
    {"category": "summarization_short", "prompt": f"TL;DR this support ticket in one sentence:\n\n{_TICKET}"},
    {"category": "summarization_short", "prompt": "Summarize in one sentence:\n\n\"After three quarters of declining engagement, the team shipped a redesigned onboarding flow in February. Activation rose 14% month-over-month, retention at day 30 improved from 21% to 26%, and support tickets about setup dropped by a third.\""},
    {"category": "summarization_short", "prompt": "Give me the key takeaways from this standup note as 3 bullets:\n\n\"Auth migration is 80% done, remaining work is the SSO edge cases. Marketing site launch slipped to Thursday because legal is still reviewing the testimonials page. The flaky payments test was traced to a timezone assumption and is fixed.\""},

    # ----- summarization_long: TRAP — simple verb, hard content (judge) -----
    {"category": "summarization_long", "prompt": f"Summarize what this clause means for a startup signing as the vendor. Plain English, one paragraph:\n\n{_LEGAL}"},
    {"category": "summarization_long", "prompt": f"Summarize the liability caps in this clause precisely — what is capped, at what amount, and what is uncapped:\n\n{_LEGAL}"},
    {"category": "summarization_long", "prompt": f"Write a root-cause summary of this incident for the postmortem doc, distinguishing trigger, root cause, and aggravating factors:\n\n{_INCIDENT}"},

    # ----- rewrite_format (judge) -----
    {"category": "rewrite_format", "prompt": "Fix the grammar without changing the meaning:\n\n\"Me and the team has went over the numbers and they wasn't matching what finance gave us.\""},
    {"category": "rewrite_format", "prompt": "Rewrite this to be more formal for an enterprise customer:\n\n\"hey! so yeah the thing broke again lol but we patched it, should be good now\""},
    {"category": "rewrite_format", "prompt": "Convert this prose into a numbered step list:\n\n\"First open settings, then go to billing, after that click payment methods and add your new card, finally remove the old one.\""},
    {"category": "rewrite_format", "prompt": "Convert this CSV row into a JSON object with keys name, role, start_date:\n\nPriya Sharma,Staff Engineer,2024-06-17", "expected": "Priya Sharma"},
    {"category": "rewrite_format", "prompt": "Make this tweet fit in 140 characters without losing the announcement:\n\n\"We are absolutely thrilled and delighted to finally announce that our long-awaited dark mode feature is now generally available to all users on every plan starting today!\""},

    # ----- codegen_simple (judge) -----
    {"category": "codegen_simple", "prompt": "Write a Python function that returns the n-th Fibonacci number iteratively."},
    {"category": "codegen_simple", "prompt": "Write a regex that matches a US ZIP code (5 digits, optional -4 extension). Show the pattern and one usage example in Python."},
    {"category": "codegen_simple", "prompt": "Write a SQL query that returns the 5 customers with the highest total order value from tables customers(id, name) and orders(id, customer_id, amount)."},
    {"category": "codegen_simple", "prompt": "Write a bash one-liner that finds all .log files over 100MB under /var and prints their sizes, largest first."},
    {"category": "codegen_simple", "prompt": "Write a Python function `dedupe_preserve_order(items)` that removes duplicates from a list while preserving first-seen order."},

    # ----- codegen_complex (judge) -----
    {"category": "codegen_complex", "prompt": "Design and implement a Python rate limiter supporting both a token-bucket and a sliding-window strategy behind one interface, with thread safety and tests. Explain the trade-offs between the two strategies."},
    {"category": "codegen_complex", "prompt": "Refactor a synchronous Flask + requests order-processing service into an async FastAPI + httpx design. Describe the migration plan (what changes, in what order, how to keep both running during cutover), then write the new order endpoint including retry logic and idempotency keys."},
    {"category": "codegen_complex", "prompt": "Implement an LRU cache with TTL expiry in Python from scratch (no functools.lru_cache): O(1) get/put, lazy expiry, a background sweep, and instrumentation hooks for hit/miss metrics. Include unit tests covering the TTL edge cases."},
    {"category": "codegen_complex", "prompt": "Design a schema and write the migrations for a multi-tenant SaaS billing system: plans, subscriptions, usage-based add-ons, proration on mid-cycle upgrades, and an audit trail. Postgres. Explain the proration approach and its edge cases."},

    # ----- debugging (judge) -----
    {"category": "debugging", "prompt": f"Based on this incident timeline, what was the root cause, and why did the rollback not fix it? What single change would have prevented the incident?\n\n{_INCIDENT}"},
    {"category": "debugging", "prompt": "This Python intermittently fails with 'RuntimeError: dictionary changed size during iteration' under load but never in tests. Explain the likely cause and fix it:\n\n```python\nactive = {}\n\ndef reap_expired(now):\n    for sid, exp in active.items():\n        if exp < now:\n            del active[sid]\n```\nThe function is called from a background thread while request handlers add sessions."},
    {"category": "debugging", "prompt": "A nightly batch job's memory usage grows ~200MB per hour until OOM, but heap profiling shows stable Python object counts. The job reads Parquet files with pandas in a loop, processes, writes results. What are the most likely causes and how would you confirm each?"},
    {"category": "debugging", "prompt": "Why does this test pass locally but deadlock in CI?\n\n```python\ndef test_concurrent_update(db_pool):\n    with db_pool.connection() as a, db_pool.connection() as b:\n        a.execute('UPDATE accounts SET bal=bal-10 WHERE id=1')\n        b.execute('UPDATE accounts SET bal=bal+10 WHERE id=2')\n        b.execute('UPDATE accounts SET bal=bal-5 WHERE id=1')\n        a.execute('UPDATE accounts SET bal=bal+5 WHERE id=2')\n```\nCI runs with a 2-connection pool; locally the pool is 10."},

    # ----- math_logic: includes TRAP — 'prove' over trivial content -----
    {"category": "math_logic", "prompt": "A SaaS plan costs $40/seat/month billed annually with a 20% discount, or monthly with none. A team of 13 wants the cheaper option for 9 months of expected use. Which is cheaper and by how much? Show the arithmetic.", "expected": "monthly"},
    {"category": "math_logic", "prompt": "Prove that the sum of two even integers is even.", },
    {"category": "math_logic", "prompt": "Prove or disprove: if a relation R on a finite set is symmetric and transitive, it must be reflexive. If false, give the smallest counterexample."},
    {"category": "math_logic", "prompt": "An A/B test shows 4.1% conversion (n=12,400) vs 4.6% (n=12,150). Is the difference statistically significant at the 95% level? Walk through the two-proportion z-test and state the conclusion."},
    {"category": "math_logic", "prompt": "You have 9 visually identical coins; one is heavier. What is the minimum number of balance-scale weighings to guarantee finding it, and why is fewer impossible?", "expected": "2"},

    # ----- agentic (judge) -----
    {"category": "agentic", "prompt": "Plan the steps to migrate 40 cron jobs from a single VM into containerized scheduled tasks: inventory, dependency mapping, secrets handling, cutover order, rollback strategy, and how you'd verify each job post-migration. Produce a concrete checklist an engineer can execute."},
    {"category": "agentic", "prompt": "You manage a release across three services with interdependent API changes. Service A's new endpoint must exist before B can deploy; C reads B's events. Design the deployment sequence with feature flags, the verification at each stage, and the abort criteria."},
    {"category": "agentic", "prompt": "Draft a runbook for on-call: 'checkout error rate above 5%'. Include triage queries, decision tree (deploy? dependency? data?), mitigation actions in order of blast radius, and when to page payments engineering."},

    # ----- analysis_strategy (judge) -----
    {"category": "analysis_strategy", "prompt": "We can build an in-house feature-flag system (~2 eng-months, then maintenance) or pay a vendor $30k/yr. 15-person engineering team, Series A, compliance is not a factor. Analyze the trade-offs and recommend, including the hidden costs each side tends to ignore."},
    {"category": "analysis_strategy", "prompt": "Our usage-based pricing causes bill shock; 8% of churned customers cite it. Sales wants seat-based pricing; finance worries about revenue from heavy users. Lay out the options (caps, committed-use discounts, hybrid), their revenue and churn risks, and a sequencing recommendation."},
    {"category": "analysis_strategy", "prompt": f"You're advising the customer in this ticket's company. Their support volume doubled in a quarter while headcount is flat. Using the ticket as an example, analyze whether better self-serve flows, AI deflection, or process changes would help most, and what you'd measure to decide:\n\n{_TICKET}"},

    # ----- creative_longform (judge) -----
    {"category": "creative_longform", "prompt": "Write a 250-word launch announcement for a developer tool that turns OpenAPI specs into typed client SDKs. Audience: backend engineers. Tone: confident, concrete, no hype words like 'revolutionary'."},
    {"category": "creative_longform", "prompt": "Write a short story (under 400 words) about a lighthouse keeper who receives a letter addressed to someone who never existed. End on an image, not an explanation."},
    {"category": "creative_longform", "prompt": "Write the opening section of a blog post titled 'The hidden cost of defaulting to your biggest model', aimed at engineering leaders. Hook with a concrete scenario, 150-200 words."},

    # ----- conversation (judge) -----
    {"category": "conversation", "prompt": "I have two job offers: a staff role at a stable company for more money, and a senior role at a risky startup with equity. I'm 29, no dependents, some savings. Help me think through how to decide — ask me the questions that actually matter."},
    {"category": "conversation", "prompt": "Help me brainstorm 10 names for an internal tool that routes AI requests to cheaper models. Mix of serious and playful."},
    {"category": "conversation", "prompt": "My standup updates ramble. Coach me: rewrite this update and tell me the pattern to follow:\n\n\"So yesterday I was looking at the thing with the cache and it turned out to be more complicated because of the invalidation stuff, anyway I also reviewed two PRs and today more of the same probably.\""},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="goldenset_data/prompts.jsonl")
    args = parser.parse_args()

    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for i, row in enumerate(CORPUS):
            f.write(json.dumps({"id": f"seed-{i:03d}", **row}) + "\n")

    # Sanity check: what the CURRENT heuristic router would do (not ground truth).
    from ..router import recommend

    predicted = Counter()
    for row in CORPUS:
        rec = recommend({"model": "claude-opus-4-8", "max_tokens": 1024,
                         "messages": [{"role": "user", "content": row["prompt"]}]})
        predicted[rec.recommended_model] += 1
    cats = Counter(r["category"] for r in CORPUS)
    print(f"wrote {len(CORPUS)} prompts -> {args.out}")
    print(f"categories ({len(cats)}): " + ", ".join(f"{c}={n}" for c, n in sorted(cats.items())))
    print("heuristic router predicted mix (sanity check, not truth): "
          + ", ".join(f"{m}={n}" for m, n in predicted.most_common()))


if __name__ == "__main__":
    main()
