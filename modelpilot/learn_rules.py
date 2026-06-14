"""Propose per-customer classification rules from this deployment's own traffic.

The global classifier sends domain-specific phrasing into the conservative
`conversation` / `unknown` catch-alls, where it is never optimized — pure
leaked savings. This command reads captured prompts (needs
MODELPILOT_CAPTURE_PCT > 0 during a run), finds the recurring topics in
catch-all traffic, quantifies how much traffic each represents, and writes a
rules scaffold you fill in with the right category.

    modelpilot learn-rules --db modelpilot.db --out rules.json
    # edit rules.json: set "category" (and optional "max_tier") per cluster
    # then:  MODELPILOT_RULES=rules.json modelpilot gateway --mode autopilot

Dependency-free: clusters by recurring salient phrases (no embeddings, no
prompts leave the box). It proposes; you confirm the category — quality stays
a human-confirmed decision, not an inferred guess.
"""

import argparse
import json
import re
import time
from collections import Counter

from .ledger import Ledger

CATCH_ALL = {"conversation", "unknown"}
# Small stopword set so mined phrases are about the task, not filler.
_STOP = frozenset((
    "the a an and or but if then this that these those of to in on for with "
    "is are was were be been being do does did have has had i you it we they "
    "he she my your our their me us them please can could would should will "
    "what how why when where which who whom into from at by as so not no yes "
    "give me write make help need want about your you're let's just like get"
).split())
_WORD = re.compile(r"[a-z][a-z0-9'+-]{2,}")


def _phrases(prompt: str) -> set[str]:
    """Salient unigrams + bigrams from one prompt (deduped per prompt so a word
    repeated within a prompt doesn't inflate document frequency)."""
    toks = [t for t in _WORD.findall(prompt.lower()) if t not in _STOP]
    out = set(toks)
    out.update(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    return out


def mine_clusters(captures: list[dict], min_docs: int = 3,
                  min_share: float = 0.05, top: int = 12) -> list[dict]:
    """Recurring phrases in catch-all captures, ranked by document frequency.

    A phrase is a candidate cluster when it appears in >= min_docs catch-all
    prompts AND in >= min_share of them. Bigrams beat their unigrams when they
    cover nearly as many docs (more specific signal makes a better rule).
    """
    catch = [c for c in captures if c["category"] in CATCH_ALL]
    if not catch:
        return []
    df = Counter()
    examples: dict[str, str] = {}
    for c in catch:
        for ph in _phrases(c["prompt"]):
            df[ph] += 1
            examples.setdefault(ph, c["prompt"])
    n = len(catch)
    candidates = [
        {"phrase": ph, "docs": cnt, "share": cnt / n, "example": examples[ph][:160]}
        for ph, cnt in df.items()
        if cnt >= min_docs and cnt / n >= min_share
    ]
    # Prefer a bigram over its component unigrams when it explains nearly as much.
    bigrams = {c["phrase"] for c in candidates if " " in c["phrase"]}
    covered = {w for bg in bigrams for w in bg.split()}
    candidates = [c for c in candidates
                  if " " in c["phrase"] or c["phrase"] not in covered]
    candidates.sort(key=lambda c: c["docs"], reverse=True)
    return candidates[:top]


def build_scaffold(clusters: list[dict]) -> dict:
    """A rules.json scaffold with category left blank for the operator to fill."""
    rules = [
        {"name": c["phrase"].replace(" ", "-"),
         "any": [c["phrase"]],
         "category": "",            # <- FILL IN: the right category for this topic
         "max_tier": None,          # optional: 0 haiku, 1 sonnet, 2 opus
         "_seen_in_pct": round(c["share"] * 100, 1),
         "_example": c["example"]}
        for c in clusters
    ]
    return {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "category_rules": rules}


def main():
    parser = argparse.ArgumentParser(description="Propose per-customer classification rules")
    parser.add_argument("--db", default="modelpilot.db")
    parser.add_argument("--days", type=float, default=30.0, help="capture window (0 = all)")
    parser.add_argument("--out", default="rules.json")
    parser.add_argument("--min-docs", type=int, default=3)
    parser.add_argument("--submit", action="store_true",
                        help="submit rules from --out (with a category filled in) to the console "
                             "for admin review, instead of (re)mining")
    args = parser.parse_args()

    if args.submit:
        from . import proposals
        try:
            with open(args.out) as f:
                rules = (json.load(f) or {}).get("category_rules", [])
        except (OSError, ValueError):
            raise SystemExit(f"No rules file at {args.out}. Run without --submit first, "
                             "fill in each rule's `category`, then re-run with --submit.")
        ready = [r for r in rules if r.get("category")]
        if not ready:
            raise SystemExit(f"No rules in {args.out} have a `category` set. Fill them in first.")
        try:
            n = proposals.submit_rules(ready)
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"Submit failed: {e}\nSet MODELPILOT_CONSOLE_URL and "
                             "MODELPILOT_DEPLOYMENT_ID.")
        print(f"Submitted {n} rule proposal(s) to the console for review.")
        return

    ledger = Ledger(args.db)
    since = time.time() - args.days * 86_400 if args.days else 0.0
    caps = ledger.captures(since)
    ledger.close()

    if not caps:
        raise SystemExit("No captured prompts. Run the gateway with "
                         "MODELPILOT_CAPTURE_PCT>0 for a while, then retry.")

    n_catch = sum(1 for c in caps if c["category"] in CATCH_ALL)
    clusters = mine_clusters(caps, min_docs=args.min_docs)
    print(f"{n_catch}/{len(caps)} captured prompts ({n_catch / len(caps):.0%}) "
          f"landed in catch-all categories — currently unoptimized.")
    if not clusters:
        raise SystemExit("No recurring topics frequent enough to propose a rule yet. "
                         "Keep capturing and re-run.")

    print("\nRecurring topics in that traffic (candidate rules):")
    for c in clusters:
        print(f"  - {c['phrase']!r}: {c['docs']} prompts ({c['share']:.0%})  "
              f"e.g. {c['example'][:70]!r}")

    with open(args.out, "w") as f:
        json.dump(build_scaffold(clusters), f, indent=2)
    print(f"\nScaffold written to {args.out}. Set the right `category` (and optional "
          f"`max_tier`) on each, then apply:\n"
          f"  MODELPILOT_RULES={args.out} modelpilot gateway --mode autopilot")


if __name__ == "__main__":
    main()
