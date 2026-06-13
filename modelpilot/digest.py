"""ModelPilot savings digest — the proactive proof that lands where the buyer
lives (Slack / email), instead of a dashboard they have to remember to open.

A cost optimizer is invisible infrastructure: the developer changes one base
URL and forgets it. The recurring value surface is this digest — a short,
buyer-facing "here's what we saved you, and quality held" summary on a cadence.

    modelpilot digest --days 7                         # print it
    modelpilot digest --days 7 --slack-webhook https://hooks.slack.com/...   # post it
    MODELPILOT_SLACK_WEBHOOK=... modelpilot digest      # same, via env
"""
from __future__ import annotations

import argparse
import os
import statistics
import time

from .ledger import Ledger
from .report import _bootstrap_diff_ci


def _usd(x: float) -> str:
    return f"${x:,.2f}" if abs(x) >= 0.01 else f"${x:,.4f}"


def build_digest(db_path: str, days: float = 7.0) -> dict:
    """Compute the buyer-facing headline numbers for a reporting window."""
    ledger = Ledger(db_path)
    try:
        since = time.time() - days * 86_400 if days else 0.0
        s = ledger.summary(since)
        esc = ledger.escalation_costs(since)
        cats = ledger.by_category(since)
        arms = ledger.arm_costs(since)
        guards = {g["arm"]: g for g in ledger.quality_guardrails(since)}
    finally:
        ledger.close()

    # Routing is "live" once anything has actually been auto-routed; before that
    # (shadow mode) the honest headline is potential, not realized, savings.
    routing_live = bool(s["n_applied"]) or s["realized"] > 0
    net_realized = s["realized"] - esc["cost"]
    headline = net_realized if routing_live else s["potential"]
    pct_baseline = (headline / s["baseline"]) if s["baseline"] else 0.0
    annualized = (headline / days * 365.0) if days else 0.0

    # Quality verdict from the randomized holdout, if it has enough data.
    control, treatment = arms["control"], arms["treatment"]
    quality: dict = {"status": "warming_up"}
    if len(control) >= 30 and len(treatment) >= 30:
        mean_t, mean_c = statistics.fmean(treatment), statistics.fmean(control)
        lo, hi = _bootstrap_diff_ci(control, treatment)
        gt, gc = guards.get("treatment", {}), guards.get("control", {})
        rate_t = (gt.get("n_negative", 0) / gt["n"]) if gt.get("n") else 0.0
        rate_c = (gc.get("n_negative", 0) / gc["n"]) if gc.get("n") else 0.0
        quality = {
            "status": "verified",
            "measured_saving_pct": ((mean_c - mean_t) / mean_c) if mean_c else 0.0,
            "ci_lo": lo, "ci_hi": hi,
            "neg_rate_routed": rate_t, "neg_rate_control": rate_c,
            "parity_held": rate_t <= rate_c + 0.02,  # within 2pp of control
        }

    return {
        "days": days,
        "routing_live": routing_live,
        "requests": s["n"],
        "switch_recs": s["n_switch_recs"],
        "applied": s["n_applied"],
        "actual": s["actual"],
        "baseline": s["baseline"],
        "headline_saved": headline,
        "net_realized": net_realized,
        "potential": s["potential"],
        "escalations": esc["n"],
        "pct_of_baseline": pct_baseline,
        "annualized": annualized,
        "top_categories": cats[:3],
        "quality": quality,
    }


def _headline_line(d: dict) -> str:
    verb = "Saved" if d["routing_live"] else "Could have saved"
    return (f"{verb} {_usd(d['headline_saved'])} "
            f"({d['pct_of_baseline']:.0%} of your Claude spend) "
            f"in the last {d['days']:g} days")


def _quality_line(d: dict) -> str:
    q = d["quality"]
    if q["status"] != "verified":
        return ("Quality monitoring: warming up (need 30+ requests in each "
                "holdout arm to certify parity).")
    if q["parity_held"]:
        return (f"Quality held: routed requests show no worse user feedback "
                f"({q['neg_rate_routed']:.1%} vs {q['neg_rate_control']:.1%} control), "
                f"verified saving {q['measured_saving_pct']:.0%}/request.")
    return (f"Quality watch: routed negative-feedback {q['neg_rate_routed']:.1%} "
            f"vs {q['neg_rate_control']:.1%} control — investigate before scaling up.")


def render_markdown(d: dict) -> str:
    """Human/email-friendly digest."""
    lines = [
        f"# ModelPilot — your Claude savings ({d['days']:g}-day digest)",
        "",
        f"**{_headline_line(d)}.**",
        "",
        f"- On track for ~{_usd(d['annualized'])}/year at this rate"
        if d["annualized"] else "",
        f"- Spend: {_usd(d['actual'])} actual vs {_usd(d['baseline'])} baseline "
        f"across {d['requests']:,} requests",
        (f"- {d['applied']:,} requests auto-routed"
         + (f", {d['escalations']} escalations charged back" if d["escalations"] else ""))
        if d["routing_live"]
        else f"- {d['switch_recs']:,} requests are safe to route (shadow mode — nothing changed yet)",
        f"- {_quality_line(d)}",
        "",
        "**Where the savings are:**",
    ]
    if d["top_categories"]:
        for c in d["top_categories"]:
            lines.append(
                f"- `{c['category']}` — {_usd(c['potential'])} "
                f"({c['n']:,} requests, avg confidence {c['avg_confidence']:.0%})"
            )
    else:
        lines.append("- No traffic recorded in this window yet.")
    return "\n".join(l for l in lines if l != "")


def render_slack(d: dict) -> dict:
    """Slack incoming-webhook payload (mrkdwn). Plain text => robust everywhere."""
    bullets = [
        f"• On track for ~{_usd(d['annualized'])}/year" if d["annualized"] else "",
        f"• {_usd(d['actual'])} spent vs {_usd(d['baseline'])} baseline · {d['requests']:,} requests",
        f"• {_quality_line(d)}",
    ]
    if d["top_categories"]:
        top = ", ".join(f"{c['category']} ({_usd(c['potential'])})" for c in d["top_categories"])
        bullets.append(f"• Top opportunities: {top}")
    text = (f"*ModelPilot — {_headline_line(d)}* :money_with_wings:\n"
            + "\n".join(b for b in bullets if b))
    return {"text": text}


def post_slack(webhook_url: str, payload: dict) -> int:
    """POST the digest to a Slack incoming webhook. Returns the HTTP status."""
    import httpx

    r = httpx.post(webhook_url, json=payload, timeout=10.0)
    r.raise_for_status()
    return r.status_code


def main():
    parser = argparse.ArgumentParser(description="ModelPilot savings digest")
    parser.add_argument("--db", default="modelpilot.db")
    parser.add_argument("--days", type=float, default=7.0, help="reporting window (0 = all time)")
    parser.add_argument("--slack-webhook", default=os.environ.get("MODELPILOT_SLACK_WEBHOOK", ""),
                        help="Slack incoming-webhook URL (or set MODELPILOT_SLACK_WEBHOOK)")
    parser.add_argument("--json", action="store_true", help="emit the raw digest dict as JSON")
    args = parser.parse_args()

    d = build_digest(args.db, args.days)
    if args.json:
        import json
        print(json.dumps(d, indent=2))
    else:
        print(render_markdown(d))

    if args.slack_webhook:
        try:
            code = post_slack(args.slack_webhook, render_slack(d))
            print(f"\nPosted to Slack (HTTP {code}).")
        except Exception as e:  # noqa: BLE001 — surface delivery failure, don't crash a cron
            print(f"\nSlack delivery failed: {e}")


if __name__ == "__main__":
    main()
