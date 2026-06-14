"""Prompt-level savings audit — savings BEYOND model choice.

Model routing isn't the only lever on a Claude bill. Two large, common, and
safe-to-recommend wins show up directly in the ledger's token accounting:

  1. Uncached repeated context. Multi-turn sessions that re-send a growing
     prefix with prompt caching OFF (cache_read_tokens stays 0 across the
     session) pay full input price every turn. Enabling `cache_control` on the
     stable prefix bills the repeat at ~10% of input price.

  2. Context bloat. Requests carrying very large input for a small output —
     oversized context relative to the work produced — where trimming or
     retrieval cuts input cost directly.

This audit only *recommends*; it never rewrites a customer's prompts (that
would be risky and is the customer's call). It quantifies the dollars at stake
from the actual tokens already billed, and points at the change. Estimates are
deliberately conservative so the number is a floor, not a sales figure.
"""

import argparse
import time
from collections import defaultdict

from .ledger import Ledger
from .pricing import CACHE_READ_MULT, resolve_price

# Thresholds (tunable). Conservative by design.
BLOAT_MIN_INPUT = 8_000      # only flag genuinely large inputs
BLOAT_RATIO = 20             # input:output ratio above which context looks oversized
BLOAT_TRIM_FRACTION = 0.30   # assume a cautious 30% of bloated input is trimmable


def _in_price(model: str) -> float | None:
    p = resolve_price(model)
    return p.input_per_mtok / 1_000_000 if p else None


def caching_opportunity(rows: list[dict]) -> dict:
    """Sessions running multi-turn with caching OFF, and the conservative dollars
    that prompt caching would have saved.

    Conservative model: within a session where cache_read stayed 0, the stable
    repeated prefix is at least the *smallest* per-turn input (the common floor
    every later turn re-sends). We credit only that floor on turns after the
    first, at the cache discount — an underestimate of the true repeated prefix.
    """
    by_session: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_session[r["session_key"]].append(r)

    total_saved = 0.0
    sessions = []
    for key, reqs in by_session.items():
        if len(reqs) < 2:
            continue
        if any(r["cache_read_tokens"] for r in reqs):
            continue  # caching already in use here
        price = _in_price(reqs[0]["original_model"])
        if not price:
            continue
        stable_prefix = min(r["input_tokens"] for r in reqs)
        if stable_prefix < 500:
            continue  # nothing worth caching
        repeats = len(reqs) - 1
        saved = stable_prefix * repeats * price * (1 - CACHE_READ_MULT)
        if saved <= 0:
            continue
        total_saved += saved
        sessions.append({"session": key[:12] or "(default)", "turns": len(reqs),
                         "stable_prefix_tokens": stable_prefix, "saved": saved})
    sessions.sort(key=lambda s: s["saved"], reverse=True)
    credited = {key for key, reqs in by_session.items()
                if len(reqs) >= 2 and not any(r["cache_read_tokens"] for r in reqs)
                and min(r["input_tokens"] for r in reqs) >= 500
                and _in_price(reqs[0]["original_model"])}
    return {"total_saved": total_saved, "n_sessions": len(sessions),
            "sessions": sessions[:10], "session_keys": credited}


def context_bloat(rows: list[dict], exclude_sessions: frozenset = frozenset()) -> dict:
    """Requests with very large input for small output — candidates for context
    trimming / retrieval. Credits only a cautious fraction of the input.

    Sessions already credited to the caching opportunity are excluded so the two
    buckets never double-count the same tokens (caching is the primary fix there).
    """
    total_saved = 0.0
    flagged = []
    for r in rows:
        if r["session_key"] in exclude_sessions:
            continue
        inp, out = r["input_tokens"], r["output_tokens"]
        if inp < BLOAT_MIN_INPUT or out <= 0 or inp / out < BLOAT_RATIO:
            continue
        price = _in_price(r["original_model"])
        if not price:
            continue
        saved = inp * BLOAT_TRIM_FRACTION * price
        total_saved += saved
        flagged.append({"id": r["id"][:8], "input_tokens": inp,
                        "output_tokens": out, "ratio": round(inp / out, 1), "saved": saved})
    flagged.sort(key=lambda f: f["saved"], reverse=True)
    return {"total_saved": total_saved, "n_requests": len(flagged), "requests": flagged[:10]}


def audit(rows: list[dict], window_days: float = 0.0) -> dict:
    cache = caching_opportunity(rows)
    bloat = context_bloat(rows, exclude_sessions=cache.get("session_keys", frozenset()))
    total = cache["total_saved"] + bloat["total_saved"]
    monthly = total / window_days * 30 if window_days else None
    return {"caching": cache, "bloat": bloat, "total_saved": total,
            "window_days": window_days, "projected_monthly": monthly,
            "n_rows": len(rows)}


def headline(report: dict) -> str | None:
    """One-line buyer-facing summary for the digest/dashboard, or None if there
    is nothing material to recommend."""
    total = report["total_saved"]
    if total < 0.01:
        return None
    bits = []
    if report["caching"]["total_saved"] > 0:
        bits.append(f"prompt caching (~${report['caching']['total_saved']:.2f} across "
                    f"{report['caching']['n_sessions']} sessions)")
    if report["bloat"]["total_saved"] > 0:
        bits.append(f"context trimming (~${report['bloat']['total_saved']:.2f} across "
                    f"{report['bloat']['n_requests']} requests)")
    proj = (f" ≈ ${report['projected_monthly']:.0f}/mo"
            if report.get("projected_monthly") else "")
    return ("Beyond model routing, you have ~$%.2f%s in prompt-level savings: %s. "
            "Run `modelpilot prompt-audit` for the details."
            % (total, proj, " and ".join(bits)))


def render(report: dict) -> str:
    lines = [f"Prompt-level savings audit ({report['n_rows']} successful requests)", ""]
    if report["total_saved"] < 0.01:
        lines.append("No material prompt-level savings found — caching looks healthy "
                     "and inputs are proportionate to outputs. Nice.")
        return "\n".join(lines)

    c = report["caching"]
    if c["total_saved"] > 0:
        lines.append(f"1. Uncached repeated context — ~${c['total_saved']:.2f} "
                     f"across {c['n_sessions']} multi-turn sessions running with caching off.")
        for s in c["sessions"][:5]:
            lines.append(f"     session {s['session']}: {s['turns']} turns, "
                         f"~{s['stable_prefix_tokens']:,}-token stable prefix "
                         f"-> ~${s['saved']:.2f}")
        lines.append("   Fix: add a `cache_control` breakpoint on your system prompt / "
                     "stable context. Repeated reads then bill at ~10%.")
        lines.append("")

    b = report["bloat"]
    if b["total_saved"] > 0:
        lines.append(f"2. Context bloat — ~${b['total_saved']:.2f} if you trimmed "
                     f"~{int(BLOAT_TRIM_FRACTION*100)}% of input on "
                     f"{b['n_requests']} oversized requests (large input, small output).")
        for r in b["requests"][:5]:
            lines.append(f"     {r['id']}: {r['input_tokens']:,} in / "
                         f"{r['output_tokens']:,} out (ratio {r['ratio']}) -> ~${r['saved']:.2f}")
        lines.append("   Fix: trim stale history or use retrieval to send only relevant context.")
        lines.append("")

    total = report["total_saved"]
    proj = (f"  (≈ ${report['projected_monthly']:.0f}/mo at this rate)"
            if report.get("projected_monthly") else "")
    lines.append(f"Total prompt-level savings available: ~${total:.2f}{proj}")
    lines.append("These are recommendations on your own billed tokens — Maven "
                 "never rewrites your prompts.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Prompt-level savings audit")
    parser.add_argument("--db", default="modelpilot.db")
    parser.add_argument("--days", type=float, default=30.0, help="window in days (0 = all)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args()

    ledger = Ledger(args.db)
    since = time.time() - args.days * 86_400 if args.days else 0.0
    rows = ledger.request_token_rows(since)
    ledger.close()

    report = audit(rows, window_days=args.days)
    if args.json:
        import json
        print(json.dumps(report, indent=2))
    else:
        print(render(report))


if __name__ == "__main__":
    main()
