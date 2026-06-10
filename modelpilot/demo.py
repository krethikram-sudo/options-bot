"""Self-contained MVP demo: gateway + autopilot routing + live savings.

  python -m modelpilot.demo                # real API (needs ANTHROPIC_API_KEY), ~25 requests
  python -m modelpilot.demo --offline      # no key, no spend — fake upstream with synthetic usage
  python -m modelpilot.demo --prompts 69 --mode advise

Spawns its own gateway on --port (default 8401, separate demo ledger), replays
a mixed workload from the seed corpus through it, prints each routing decision
as it happens, then summarizes and leaves the gateway up so you can browse
http://127.0.0.1:<port>/modelpilot/dashboard. Ctrl-C to stop.

Live-mode cost: ~25 short prompts at max_tokens=256 is well under $1.
"""

import argparse
import json
import os
import random
import signal
import subprocess
import sys
import threading
import time

import httpx

# SIGTERM must run the finally-block cleanup, or the spawned gateway outlives
# the demo and squats on the port for the next run.
signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))

from .goldenset.seed_corpus import CORPUS

BASELINE_MODEL = "claude-opus-4-8"


# ---------------------------------------------------------------------------
# Offline upstream: answers like the API, costs nothing
# ---------------------------------------------------------------------------

def start_fake_upstream(port: int):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    rng = random.Random(7)

    class FakeUpstream(BaseHTTPRequestHandler):
        # HTTP/1.1 keep-alive — the gateway pools connections, and a
        # close-after-response HTTP/1.0 server races it into resets.
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            approx_in = max(len(json.dumps(body.get("messages", []))) // 4, 50)
            resp = json.dumps({
                "id": "msg_demo", "type": "message", "role": "assistant",
                "model": body.get("model"), "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "(offline demo response)"}],
                "usage": {"input_tokens": approx_in,
                          "output_tokens": rng.randint(80, 400),
                          "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0},
            }).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), FakeUpstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _port_in_use(port: int) -> bool:
    try:
        httpx.get(f"http://127.0.0.1:{port}/modelpilot/stats", timeout=1)
        return True
    except httpx.HTTPError:
        return False


def start_gateway(port: int, mode: str, db: str, upstream: str,
                  holdout: float = 0.0) -> subprocess.Popen:
    if _port_in_use(port):
        raise SystemExit(
            f"Port {port} already has a gateway on it (a previous demo still running?).\n"
            f"Kill it or pass --port with a free port."
        )
    env = {**os.environ,
           "MODELPILOT_MODE": mode,
           "MODELPILOT_DB": db,
           "MODELPILOT_UPSTREAM": upstream,
           # Demo default: no holdout, so interactive chat always routes —
           # pass --holdout 0.1 to demonstrate the RCT control arm instead.
           "MODELPILOT_HOLDOUT_PCT": str(holdout),
           "MODELPILOT_CAPTURE_PCT": "0"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "modelpilot.gateway:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        env=env,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"gateway exited with code {proc.returncode} during startup")
        if _port_in_use(port):
            return proc
        time.sleep(0.3)
    proc.terminate()
    raise RuntimeError("gateway did not come up within 20s")


def run_workload(port: int, api_key: str, prompts: list[dict], max_tokens: int):
    base = f"http://127.0.0.1:{port}"
    client = httpx.Client(timeout=120.0)
    print(f"\n{'#':>3} {'category':<22} {'decision':<9} {'ran on':<20} {'conf':>5}  rationale")
    print("-" * 100)
    for i, row in enumerate(prompts, 1):
        request = dict(
            url=f"{base}/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "x-session-id": f"demo-{i}"},
            json={"model": BASELINE_MODEL, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": row["prompt"]}]},
        )
        try:
            resp = client.post(**request)
        except httpx.TransportError:
            resp = client.post(**request)  # one retry on transient resets
        h = resp.headers
        ran_on = h.get("x-modelpilot-routed-model", BASELINE_MODEL)
        action = h.get("x-modelpilot-action", "stay")
        decision = "SWITCH" if ran_on != BASELINE_MODEL else ("advise" if action == "switch" else "stay")
        arm = h.get("x-modelpilot-arm", "")
        if arm == "control":
            decision = "control"
        status = "" if resp.status_code == 200 else f"  [HTTP {resp.status_code}]"
        print(f"{i:>3} {row['category']:<22} {decision:<9} {ran_on:<20} "
              f"{h.get('x-modelpilot-confidence', '—'):>5}  {h.get('x-modelpilot-category', '')}{status}")
    client.close()


def print_summary(port: int):
    stats = httpx.get(f"http://127.0.0.1:{port}/modelpilot/stats?days=0", timeout=5).json()
    s = stats["summary"]
    print("\n" + "=" * 60)
    print(f"requests: {s['n']}   actual spend: ${s['actual']:.4f}   "
          f"baseline: ${s['baseline']:.4f}")
    print(f"REALIZED savings: ${s['realized']:.4f}   "
          f"POTENTIAL: ${s['potential']:.4f}"
          + (f"   ({s['potential'] / s['baseline']:.0%} of baseline)" if s["baseline"] else ""))
    print(f"\nDashboard:  http://127.0.0.1:{port}/modelpilot/dashboard?days=0")
    print(f"Chat live:  http://127.0.0.1:{port}/modelpilot/chat   (type your own prompts)")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="no API key, no spend")
    parser.add_argument("--mode", default="autopilot", choices=["shadow", "advise", "autopilot"])
    parser.add_argument("--port", type=int, default=8401)
    parser.add_argument("--prompts", type=int, default=25)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--db", default="modelpilot_demo.db")
    parser.add_argument("--fresh", action="store_true", help="start with an empty demo ledger")
    parser.add_argument("--holdout", type=float, default=0.0,
                        help="control-arm fraction (default 0 so chat always routes)")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not args.offline and not api_key:
        sys.exit("ANTHROPIC_API_KEY is not set. Set it, or run with --offline (no spend).")
    if args.fresh and os.path.exists(args.db):
        os.remove(args.db)

    upstream = "https://api.anthropic.com"
    fake = None
    if args.offline:
        fake = start_fake_upstream(args.port + 1)
        upstream = f"http://127.0.0.1:{args.port + 1}"
        api_key = "offline-demo-key"

    rng = random.Random(11)
    prompts = rng.sample(CORPUS, min(args.prompts, len(CORPUS)))

    print(f"Starting gateway on :{args.port}  mode={args.mode}  "
          f"upstream={'OFFLINE (synthetic)' if args.offline else 'api.anthropic.com'}")
    proc = start_gateway(args.port, args.mode, args.db, upstream, holdout=args.holdout)
    try:
        run_workload(args.port, api_key, prompts, args.max_tokens)
        print_summary(args.port)
        print("\nGateway still running — browse the dashboard, then Ctrl-C to stop.")
        proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        if fake:
            fake.shutdown()


if __name__ == "__main__":
    main()
