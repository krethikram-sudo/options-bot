"""ModelPilot command-line interface.

  modelpilot gateway [--mode shadow|advise|autopilot] [--port 8400] ...
  modelpilot demo [--offline] [...]        # self-contained two-minute demo
  modelpilot report [--days 7] [...]       # savings report in the terminal
  modelpilot share                         # redacted summary for bug reports

The gateway flags map onto the MODELPILOT_* environment variables, so launchd/
systemd deployments that set env directly behave identically.
"""

import argparse
import os
import platform
import sys
import time

from . import __version__


def _gateway_env(args) -> dict:
    env = {
        "MODELPILOT_MODE": args.mode,
        "MODELPILOT_DB": args.db,
        "MODELPILOT_UPSTREAM": args.upstream,
        "MODELPILOT_CONFIDENCE": str(args.confidence),
        "MODELPILOT_HOLDOUT_PCT": str(args.holdout),
        "MODELPILOT_CAPTURE_PCT": str(args.capture),
    }
    return env


def cmd_gateway(args):
    os.environ.update(_gateway_env(args))
    import uvicorn

    print(f"ModelPilot {__version__} — {args.mode} mode on http://127.0.0.1:{args.port}")
    print(f"  dashboard: http://127.0.0.1:{args.port}/modelpilot/dashboard")
    print(f"  chat:      http://127.0.0.1:{args.port}/modelpilot/chat")
    uvicorn.run("modelpilot.gateway:app", host="127.0.0.1", port=args.port,
                log_level="warning")


def _delegate(main_fn, rest):
    sys.argv = ["modelpilot"] + rest
    main_fn()


def share_report(db_path: str) -> str:
    """Redacted diagnostics for feedback/issues: counts and dollars only —
    never prompt text, model outputs, or keys."""
    from .ledger import Ledger

    ledger = Ledger(db_path)
    s = ledger.summary()
    esc = ledger.escalation_costs()
    lines = [
        "### ModelPilot beta report (redacted — no prompt text included)",
        f"- version: {__version__} · python {platform.python_version()} · {platform.system()}",
        f"- requests scored: {s['n']:,}  (switch recs: {s['n_switch_recs']:,}, applied: {s['n_applied']:,})",
        f"- actual spend ${s['actual']:.2f} vs baseline ${s['baseline']:.2f}",
        f"- realized savings ${s['realized']:.2f} (net ${s['realized'] - esc['cost']:.2f} "
        f"after {esc['n']} escalations) · potential ${s['potential']:.2f}",
        "",
        "| category | n | potential $ | avg conf |",
        "|---|---|---|---|",
    ]
    for row in ledger.by_category()[:12]:
        lines.append(f"| {row['category']} | {row['n']} | {row['potential']:.4f} "
                     f"| {row['avg_confidence']:.2f} |")
    ledger.close()
    return "\n".join(lines)


def cmd_share(args):
    print(share_report(args.db))
    print("\nPaste the above into a GitHub issue — and add the chip text + a "
          "description of the prompt (not the prompt itself) for routing misses.")


def main():
    parser = argparse.ArgumentParser(prog="modelpilot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"modelpilot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("gateway", help="run the routing gateway")
    g.add_argument("--mode", default="shadow", choices=["shadow", "advise", "autopilot"])
    g.add_argument("--port", type=int, default=8400)
    g.add_argument("--db", default="modelpilot.db")
    g.add_argument("--upstream", default="https://api.anthropic.com")
    g.add_argument("--confidence", type=float, default=0.8, help="autopilot gate")
    g.add_argument("--holdout", type=float, default=0.10, help="RCT control fraction")
    g.add_argument("--capture", type=float, default=0.0,
                   help="opt-in prompt-capture sampling for tuning (default 0 = never)")
    g.set_defaults(fn=cmd_gateway)

    d = sub.add_parser("demo", help="self-contained two-minute demo")
    d.add_argument("rest", nargs=argparse.REMAINDER)
    d.set_defaults(fn=lambda a: _delegate(__import__("modelpilot.demo", fromlist=["main"]).main, a.rest))

    r = sub.add_parser("report", help="savings report")
    r.add_argument("rest", nargs=argparse.REMAINDER)
    r.set_defaults(fn=lambda a: _delegate(__import__("modelpilot.report", fromlist=["main"]).main, a.rest))

    c = sub.add_parser("compare", help="side-by-side proof: routed vs all-baseline")
    c.add_argument("rest", nargs=argparse.REMAINDER)
    c.set_defaults(fn=lambda a: _delegate(__import__("modelpilot.compare", fromlist=["main"]).main, a.rest))

    s = sub.add_parser("share", help="redacted diagnostics for feedback")
    s.add_argument("--db", default="modelpilot.db")
    s.set_defaults(fn=cmd_share)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
