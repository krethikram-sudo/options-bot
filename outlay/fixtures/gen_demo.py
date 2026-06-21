#!/usr/bin/env python3
"""Generate the rich demo dataset used by `sample_report()` (the one-click
populated dashboard a prospect sees before connecting any keys).

Deliberately SEPARATE from the small, deterministic test fixtures
(`github_issues.json` / `anthropic_usage.json`) — tests assert exact numbers on
those, so the demo gets its own files: `demo_github_issues.json` +
`demo_anthropic_usage.json`. Re-generate with `python -m outlay.fixtures.gen_demo`.

Realism goals (so the demo earns trust instead of undermining it):
  * Several teams + epics, dozens of closed tickets per class → the accuracy
    backtest has enough history to show a believable error (not 200%+ on 6 rows).
  * Cache-heavy agentic events (cache reads dominate) → cache-aware costing is
    visibly the right number.
  * ~88% ticket coverage (most events carry a branch; some sessions drop it mid-
    way → session propagation recovers them; a little pure team/invoice spend).
  * A couple of honest outliers so an anomaly flag has something real to show.
"""
from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

SEED = 7
BASE = dt.datetime(2026, 6, 20, 18, 0, 0, tzinfo=dt.timezone.utc)  # "today-ish"

TEAMS = {
    "platform": ["alice@acme.dev", "raj@acme.dev", "mei@acme.dev"],
    "growth":   ["bob@acme.dev", "sara@acme.dev"],
    "payments": ["diego@acme.dev", "nina@acme.dev"],
    "mobile":   ["liam@acme.dev", "yuki@acme.dev"],
}
EPIC = {"platform": "Q3 Stability", "growth": "Billing v2",
        "payments": "Payments hardening", "mobile": "Mobile GA"}

# class → (github label, branch prefix, mean agent turns, lognormal sigma)
CLASSES = {
    "bug":      ("bug",      "fix",      6,  0.4),
    "feature":  ("feature",  "feature",  18, 0.35),
    "refactor": ("refactor", "refactor", 12, 0.32),
    "test":     ("test",     "test",     6,  0.4),
    "chore":    ("chore",    "chore",    4,  0.45),
}
CLOSED = {"bug": 20, "feature": 14, "refactor": 10, "test": 8, "chore": 6}
OPEN   = {"bug": 5,  "feature": 6,  "refactor": 2, "test": 2, "chore": 3}

TITLES = {
    "bug": ["NullPointer in {} parser", "Flaky retry under load on {}", "Off-by-one in {} pagination",
            "Race condition in {} cache", "{} webhook signature mismatch", "Timeout on large {} export",
            "Incorrect {} rounding", "Memory leak in {} worker", "Crash on empty {} payload"],
    "feature": ["Add OAuth login to {}", "{} usage export to CSV", "SSO/SCIM provisioning for {}",
                "Self-serve {} budgets", "Real-time {} dashboard", "Bulk {} import",
                "{} audit-log streaming", "Configurable {} retention"],
    "refactor": ["Extract {} into a service", "Split the {} monolith module", "Migrate {} to async",
                 "Consolidate {} clients", "Type the {} boundary"],
    "test": ["Coverage for {} retry path", "Integration tests for {}", "Fuzz the {} parser",
             "Snapshot tests for {}", "Load test {}"],
    "chore": ["Bump {} deps", "Update {} API docs", "Tidy {} config", "Format the {} package"],
}
NOUNS = ["order", "billing", "auth", "pricing", "invoice", "report", "webhook", "ledger",
         "checkout", "payout", "notification", "sync", "search", "upload"]

MODELS_W = (["claude-opus-4-8"] * 6) + ["claude-sonnet-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]


def _ts(days_ago: float, hour: int) -> str:
    t = BASE - dt.timedelta(days=days_ago) + dt.timedelta(hours=hour - 18)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _turn(rng: random.Random, model: str) -> dict:
    """One cache-heavy agentic turn's token usage."""
    scale = {"claude-opus-4-8": 1.0, "claude-sonnet-4-6": 0.8, "claude-haiku-4-5": 0.5}[model]
    return {
        "input_tokens": int(rng.randint(15_000, 35_000) * scale),
        "output_tokens": int(rng.randint(4_000, 12_000) * scale),
        "cache_read_input_tokens": int(rng.randint(1_800_000, 3_800_000) * scale),
        "cache_creation_input_tokens": int(rng.randint(120_000, 280_000) * scale),
    }


def main() -> None:
    rng = random.Random(SEED)
    issues: list[dict] = []
    records: list[dict] = []
    num = 200

    team_cycle = {t: iter_round(members) for t, members in TEAMS.items()}
    teams = list(TEAMS)

    # ---- closed tickets (history → backtest + spend breakdown) ----
    for cls, count in CLOSED.items():
        label, brpfx, mean_turns, sigma = CLASSES[cls]
        for _ in range(count):
            team = rng.choice(teams)
            user = next(team_cycle[team])
            noun = rng.choice(NOUNS)
            title = rng.choice(TITLES[cls]).format(noun)
            n = max(1, round(rng.lognormvariate(0, sigma) * mean_turns))
            # rare honest outlier: a ticket that ran away (anomaly flag fodder)
            if rng.random() < 0.035:
                n = int(n * rng.uniform(3, 4.5))
            created = rng.uniform(6, 26)
            merged = created - rng.uniform(0.5, 4)
            issues.append({
                "number": num, "title": title, "state": "closed",
                "created_at": _ts(created, 9), "merged_at": _ts(max(0.2, merged), 16),
                "labels": [label], "head_ref": f"{brpfx}/{num}-{noun}", "team": team,
                "milestone": {"title": EPIC[team]},
                "additions": rng.randint(8, 700), "deletions": rng.randint(2, 300),
            })
            sess = f"s{num}"
            for k in range(n):
                model = rng.choice(MODELS_W)
                day = merged - (n - k) * 0.04
                ev = {
                    "id": f"e{num}_{k}", "model": model, "timestamp": _ts(max(0.1, day), 9 + (k % 8)),
                    "usage": _turn(rng, model),
                    "metadata": {"user": user, "session_id": sess},
                }
                # Coverage realism: most turns carry the branch; ~1/4 of later turns
                # drop it (session propagation recovers them); the very first turn of
                # some sessions carries the explicit tag (CALL).
                if k == 0 and rng.random() < 0.3:
                    ev["metadata"]["ticket"] = f"GH-{num}"
                elif k < 2 or rng.random() > 0.25:
                    ev["metadata"]["branch"] = f"{brpfx}/{num}-{noun}"
                records.append(ev)
            num += 1

    # ---- a little unattributed spend (TEAM + INVOICE) for honest coverage ----
    # Personal-branch / trunk-based sessions: real agent work with no ticket signal
    # → resolves to a team but no ticket (the honest coverage gap a prospect sees).
    for i in range(8):
        team = rng.choice(teams)
        user = next(team_cycle[team])
        for k in range(rng.randint(2, 4)):
            model = rng.choice(MODELS_W)
            records.append({
                "id": f"e_team{i}_{k}", "model": model, "timestamp": _ts(rng.uniform(1, 20), 20 + k % 3),
                "usage": _turn(rng, model), "metadata": {"user": user, "session_id": f"sx{i}"},
            })
    for i in range(4):
        records.append({
            "id": f"e_inv{i}", "model": "claude-sonnet-4-6", "timestamp": _ts(rng.uniform(1, 20), 23),
            "usage": {"input_tokens": 40_000, "output_tokens": 9_000,
                      "cache_read_input_tokens": 600_000, "cache_creation_input_tokens": 60_000},
        })

    # ---- open tickets (forecast targets) ----
    for cls, count in OPEN.items():
        label, brpfx, _, _ = CLASSES[cls]
        for _ in range(count):
            team = rng.choice(teams)
            noun = rng.choice(NOUNS)
            issues.append({
                "number": num, "title": rng.choice(TITLES[cls]).format(noun), "state": "open",
                "created_at": _ts(rng.uniform(0.5, 6), 9),
                "labels": [label] + (["in progress"] if rng.random() < 0.4 else []),
                "head_ref": f"{brpfx}/{num}-{noun}", "team": team, "milestone": {"title": EPIC[team]},
            })
            num += 1

    out = Path(__file__).resolve().parent
    (out / "demo_github_issues.json").write_text(json.dumps({"issues": issues}, indent=0) + "\n")
    (out / "demo_anthropic_usage.json").write_text(json.dumps({"records": records}, indent=0) + "\n")
    print(f"wrote {len(issues)} issues, {len(records)} usage events")


def iter_round(items):
    """Round-robin iterator over a list (so users spread across their team)."""
    i = 0
    while True:
        yield items[i % len(items)]
        i += 1


if __name__ == "__main__":
    main()
