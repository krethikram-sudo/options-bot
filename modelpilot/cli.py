"""ModelPilot command-line interface.

  modelpilot gateway [--mode shadow|advise|autopilot] [--port 8400] ...
  modelpilot demo [--offline] [...]        # self-contained two-minute demo
  modelpilot report [--days 7] [...]       # savings report in the terminal
  modelpilot digest [--days 7] [--slack-webhook ...]  # buyer-facing savings digest
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


# Subcommands that own their full flag set. Dispatched before argparse:
# REMAINDER positionals don't reliably capture leading --flags, so a plain
# `modelpilot demo --offline` would die with "unrecognized arguments".
_DELEGATED = {
    "demo": "modelpilot.demo",
    "report": "modelpilot.report",
    "compare": "modelpilot.compare",
    "replay": "modelpilot.replay",
    "digest": "modelpilot.digest",
    "tune": "modelpilot.tune",
}


def _dispatch_delegated(argv) -> bool:
    if len(argv) > 1 and argv[1] in _DELEGATED:
        import importlib

        module = importlib.import_module(_DELEGATED[argv[1]])
        sys.argv = [f"modelpilot {argv[1]}"] + argv[2:]
        module.main()
        return True
    return False


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modelpilot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"modelpilot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("gateway", help="run the routing gateway")
    # Defaults fall back to the MODELPILOT_* env vars so an explicit flag
    # overrides env, env overrides the built-in default, and a flag we then
    # re-export in _gateway_env never clobbers an env var the user already set.
    g.add_argument("--mode", default=os.environ.get("MODELPILOT_MODE", "shadow"),
                   choices=["shadow", "guidance", "advise", "autopilot"],
                   help="guidance (recommend, change nothing) -> autopilot (auto-route)")
    g.add_argument("--port", type=int, default=int(os.environ.get("MODELPILOT_PORT", "8400")))
    g.add_argument("--db", default=os.environ.get("MODELPILOT_DB", "modelpilot.db"))
    g.add_argument("--upstream", default=os.environ.get("MODELPILOT_UPSTREAM", "https://api.anthropic.com"))
    g.add_argument("--confidence", type=float,
                   default=float(os.environ.get("MODELPILOT_CONFIDENCE", "0.8")), help="autopilot gate")
    g.add_argument("--holdout", type=float,
                   default=float(os.environ.get("MODELPILOT_HOLDOUT_PCT", "0.10")), help="RCT control fraction")
    g.add_argument("--capture", type=float,
                   default=float(os.environ.get("MODELPILOT_CAPTURE_PCT", "0.0")),
                   help="opt-in prompt-capture sampling for tuning (default 0 = never)")
    g.set_defaults(fn=cmd_gateway)

    # Delegated subcommands (handled by _dispatch_delegated; listed for --help)
    sub.add_parser("demo", help="self-contained two-minute demo")
    sub.add_parser("report", help="savings report")
    sub.add_parser("compare", help="side-by-side proof: routed vs all-baseline")
    sub.add_parser("replay", help="Layer-2 calibration: replay samples on the baseline")
    sub.add_parser("digest", help="buyer-facing savings digest (print or post to Slack)")
    sub.add_parser("tune", help="learn a per-customer routing policy from your own traffic")

    s = sub.add_parser("share", help="redacted diagnostics for feedback")
    s.add_argument("--db", default=os.environ.get("MODELPILOT_DB", "modelpilot.db"))
    s.set_defaults(fn=cmd_share)
    return parser


def main():
    if _dispatch_delegated(sys.argv):
        return
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
