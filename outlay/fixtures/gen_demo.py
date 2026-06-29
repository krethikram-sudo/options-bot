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
    "platform": ["alice@acme.dev", "raj@acme.dev", "mei@acme.dev", "tomas@acme.dev"],
    "growth":   ["bob@acme.dev", "sara@acme.dev", "ivan@acme.dev"],
    "payments": ["diego@acme.dev", "nina@acme.dev", "priya@acme.dev"],
    "mobile":   ["liam@acme.dev", "yuki@acme.dev", "omar@acme.dev"],
    "data":     ["wei@acme.dev", "hana@acme.dev", "luca@acme.dev"],
    "infra":    ["karl@acme.dev", "fatima@acme.dev", "sven@acme.dev"],
    "search":   ["jin@acme.dev", "noor@acme.dev"],
    "checkout": ["paolo@acme.dev", "grace@acme.dev"],
}
EPIC = {"platform": "Q3 Stability", "growth": "Billing v2",
        "payments": "Payments hardening", "mobile": "Mobile GA",
        "data": "Warehouse migration", "infra": "Cluster autoscaling",
        "search": "Relevance v3", "checkout": "One-click checkout"}

# API keys the org's spend is billed under, stamped on every usage event so the
# work-vs-non-work surface has real per-key metadata to group and tag. One prod
# key per team carries that team's ticketed work; a shared off-hours
# `personal_sandbox` key carries only unattributed, late-night, no-ticket
# sessions — the natural key a customer tags "Personal" to see (and stop) non-work
# spend. A `batch_jobs` key holds the unattended/eval spend. Metadata only — no
# prompt content is ever involved in the split.
PERSONAL_KEY = "key_personal_sandbox"
BATCH_KEY = "key_batch_jobs"


def _team_key(team: str) -> str:
    return f"key_{team}_prod"

# Token volume multiplier on every agentic turn. Real coding-agent sessions on a
# large monorepo carry very large cached context (millions of cache-read tokens per
# turn); this knob scales the worked demo to a believable mid-size-org quarter
# (~$80–110k) without changing the *shape* of the data. Tune and re-generate.
TOKEN_SCALE = 7.7

# class → (github label, branch prefix, mean agent turns, lognormal sigma)
CLASSES = {
    "bug":      ("bug",      "fix",      11,  0.4),
    "feature":  ("feature",  "feature",  38, 0.35),
    "refactor": ("refactor", "refactor", 22, 0.32),
    "test":     ("test",     "test",     11,  0.4),
    "chore":    ("chore",    "chore",    7,  0.45),
}
# Roughly a quarter of delivery for a ~25-engineer org: a few hundred closed
# tickets across eight teams, enough to make every breakdown look populated and
# the accuracy backtest land on a believable error.
CLOSED = {"bug": 64, "feature": 46, "refactor": 32, "test": 26, "chore": 20}
OPEN   = {"bug": 16, "feature": 18, "refactor": 8,  "test": 7,  "chore": 9}

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

_FIB = [1, 2, 3, 5, 8, 13, 21]


def _fib(x: float) -> int:
    """Snap a positive number to the nearest Fibonacci story-point value."""
    return min(_FIB, key=lambda f: abs(f - x))


def _points(rng: random.Random, mean_turns: int) -> int:
    """A story-point estimate that tracks effort closely (low noise), so the size
    model learns a real points→cost slope and *beats* the work-type mean in the
    accuracy back-test — the demo shows size-conditioning actually sharpening the
    forecast, not just matching."""
    return _fib(rng.lognormvariate(0, 0.12) * mean_turns / 3.0)


def _ts(days_ago: float, hour: int) -> str:
    t = BASE - dt.timedelta(days=days_ago) + dt.timedelta(hours=hour - 18)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _turn(rng: random.Random, model: str) -> dict:
    """One cache-heavy agentic turn's token usage."""
    scale = {"claude-opus-4-8": 1.0, "claude-sonnet-4-6": 0.8, "claude-haiku-4-5": 0.5}[model]
    scale *= TOKEN_SCALE
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
                "milestone": {"title": EPIC[team]}, "points": _points(rng, n),
                "additions": rng.randint(8, 700), "deletions": rng.randint(2, 300),
            })
            sess = f"s{num}"
            for k in range(n):
                model = rng.choice(MODELS_W)
                day = merged - (n - k) * 0.04
                ev = {
                    "id": f"e{num}_{k}", "model": model, "timestamp": _ts(max(0.1, day), 9 + (k % 8)),
                    "usage": _turn(rng, model),
                    "metadata": {"user": user, "session_id": sess, "api_key_id": _team_key(team)},
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
    for i in range(120):
        team = rng.choice(teams)
        user = next(team_cycle[team])
        for k in range(rng.randint(2, 4)):
            model = rng.choice(MODELS_W)
            records.append({
                "id": f"e_team{i}_{k}", "model": model, "timestamp": _ts(rng.uniform(1, 20), 20 + k % 3),
                "usage": _turn(rng, model),
                "metadata": {"user": user, "session_id": f"sx{i}", "api_key_id": _team_key(team)},
            })

    # ---- personal / side-project spend on a shared off-hours key ----
    # Late-night, no-ticket sessions a few engineers ran on a shared sandbox key —
    # the believable non-work spend a customer tags "Personal" and then stops per
    # team. Resolves to the engineer's team (so per-team enforcement has something
    # to act on) but never to a ticket, so it reads as unknown until the key is
    # tagged. ~6-7% of spend — visible enough to tell the story, small enough to be
    # honest. Metadata only; the split never inspects a prompt.
    personal_users = ["bob@acme.dev", "karl@acme.dev", "yuki@acme.dev", "luca@acme.dev", "grace@acme.dev"]
    for i in range(40):
        user = personal_users[i % len(personal_users)]
        for k in range(rng.randint(4, 7)):
            model = rng.choice(MODELS_W)
            records.append({
                "id": f"e_personal{i}_{k}", "model": model, "timestamp": _ts(rng.uniform(1, 20), 21 + k % 3),
                "usage": _turn(rng, model),
                "metadata": {"user": user, "session_id": f"sp{i}", "api_key_id": PERSONAL_KEY},
            })

    for i in range(40):
        records.append({
            "id": f"e_inv{i}", "model": "claude-sonnet-4-6", "timestamp": _ts(rng.uniform(1, 20), 23),
            "usage": {"input_tokens": int(40_000 * TOKEN_SCALE), "output_tokens": int(9_000 * TOKEN_SCALE),
                      "cache_read_input_tokens": int(600_000 * TOKEN_SCALE),
                      "cache_creation_input_tokens": int(60_000 * TOKEN_SCALE)},
            "metadata": {"api_key_id": BATCH_KEY},
        })

    # ---- open tickets (forecast / backlog-estimate targets) ----
    for cls, count in OPEN.items():
        label, brpfx, mean_turns, _ = CLASSES[cls]
        for _ in range(count):
            team = rng.choice(teams)
            noun = rng.choice(NOUNS)
            issue = {
                "number": num, "title": rng.choice(TITLES[cls]).format(noun), "state": "open",
                "created_at": _ts(rng.uniform(0.5, 6), 9),
                "labels": [label] + (["in progress"] if rng.random() < 0.4 else []),
                "head_ref": f"{brpfx}/{num}-{noun}", "team": team, "milestone": {"title": EPIC[team]},
            }
            # Most planned tickets carry a point estimate → the backlog prices at high
            # confidence and varied amounts; ~1 in 4 has none (priced at the class mean,
            # so the demo shows a realistic mix of confidence tiers).
            if rng.random() > 0.25:
                issue["points"] = _points(rng, mean_turns)
            issues.append(issue)
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
