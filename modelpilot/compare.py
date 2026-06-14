"""Side-by-side proof: routed vs all-baseline on the same prompt set.

  modelpilot compare --offline                       # report shape, no spend
  modelpilot compare --prompts mine.jsonl            # your prompts, real API
  modelpilot compare --judge                         # + non-inferiority verdicts

Runs every prompt twice — once on the model ModelPilot routes it to, once
entirely on the baseline (default claude-fable-5) — then writes an HTML
report showing, per prompt: both outputs side by side, actual token costs,
and (with --judge) a position-debiased non-inferiority verdict. The summary
states total cost per arm, savings %, and the non-inferior rate.

This is the trust artifact: savings AND outputs, same prompts, same page.
Live cost for 20 short prompts is typically a few dollars (both arms +
judging); --offline costs nothing.
"""

import argparse
import html
import json
import os
import random
import sys
import time

from .pricing import Usage, request_cost
from .router import recommend

DEFAULT_BASELINE = "claude-fable-5"
CONFIDENCE_GATE = 0.8


# ---------------------------------------------------------------------------
# Execution backends (injectable for tests / offline)
# ---------------------------------------------------------------------------

def offline_run_fn(model: str, prompt: str):
    rng = random.Random(hash((model, prompt)) & 0xFFFF)
    text = (f"[offline sample output from {model}]\n"
            f"Response to: {prompt[:80]}…")
    usage = Usage(input_tokens=max(len(prompt) // 4, 30),
                  output_tokens=rng.randint(80, 400))
    return text, usage


def api_run_fn(api_key: str, max_tokens: int = 1024):
    import httpx

    client = httpx.Client(timeout=180.0)

    def run(model: str, prompt: str):
        resp = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json={"model": model, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
        return text, Usage.from_api(data.get("usage") or {})

    return run


def offline_judge_fn(prompt, baseline_text, routed_text):
    return random.Random(hash(prompt) & 0xFFFF).random() > 0.05


def api_judge_fn():
    import anthropic

    from .goldenset.judge import judge_pair

    client = anthropic.Anthropic()

    def judge(prompt, baseline_text, routed_text):
        return judge_pair(client, prompt, baseline_text, routed_text)

    return judge


# ---------------------------------------------------------------------------
# The comparison
# ---------------------------------------------------------------------------

def run_comparison(prompts: list[dict], baseline: str, run_fn,
                   judge_fn=None, gate: float = CONFIDENCE_GATE,
                   progress=print) -> dict:
    rows = []
    for i, p in enumerate(prompts, 1):
        body = {"model": baseline, "max_tokens": 1024,
                "messages": [{"role": "user", "content": p["prompt"]}]}
        rec = recommend(body)
        routed_model = (rec.recommended_model
                        if rec.action == "switch" and rec.confidence >= gate
                        else baseline)
        progress(f"[{i}/{len(prompts)}] {rec.category:<22} -> {routed_model}")
        routed_text, routed_usage = run_fn(routed_model, p["prompt"])
        base_text, base_usage = run_fn(baseline, p["prompt"])
        verdict = None
        if judge_fn is not None and routed_model != baseline:
            verdict = judge_fn(p["prompt"], base_text, routed_text)
        rows.append({
            "id": p.get("id", f"p{i}"),
            "prompt": p["prompt"],
            "category": rec.category,
            "confidence": rec.confidence,
            "baseline_model": baseline,
            "routed_model": routed_model,
            "switched": routed_model != baseline,
            "baseline_text": base_text,
            "routed_text": routed_text,
            "baseline_cost": request_cost(baseline, base_usage) or 0.0,
            "routed_cost": request_cost(routed_model, routed_usage) or 0.0,
            "non_inferior": verdict,
        })

    total_base = sum(r["baseline_cost"] for r in rows)
    total_routed = sum(r["routed_cost"] for r in rows)
    judged = [r for r in rows if r["non_inferior"] is not None]
    return {
        "baseline": baseline,
        "n": len(rows),
        "n_switched": sum(r["switched"] for r in rows),
        "total_baseline_cost": total_base,
        "total_routed_cost": total_routed,
        "savings": total_base - total_routed,
        "savings_pct": (total_base - total_routed) / total_base if total_base else 0.0,
        "n_judged": len(judged),
        "non_inferior_rate": (sum(r["non_inferior"] for r in judged) / len(judged)
                              if judged else None),
        "rows": rows,
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
    }


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def render_report(result: dict) -> str:
    e = html.escape
    usd = lambda x: f"${x:,.4f}" if abs(x) < 0.01 else f"${x:,.2f}"
    nir = result["non_inferior_rate"]
    cards = f"""
    <div class="cards">
      <div class="card hero"><div class="num save">{usd(result['savings'])}
        ({result['savings_pct']:.0%})</div><div class="label">saved vs all-{e(result['baseline'])}</div></div>
      <div class="card"><div class="num">{usd(result['total_routed_cost'])}</div>
        <div class="label">routed cost ({result['n']} prompts, {result['n_switched']} switched)</div></div>
      <div class="card"><div class="num">{usd(result['total_baseline_cost'])}</div>
        <div class="label">all-baseline cost</div></div>
      <div class="card"><div class="num">{f"{nir:.0%}" if nir is not None else "—"}</div>
        <div class="label">outputs judged non-inferior{f" ({result['n_judged']} judged)" if result['n_judged'] else " (run with --judge)"}</div></div>
    </div>"""

    blocks = []
    for r in result["rows"]:
        verdict = ("" if r["non_inferior"] is None else
                   ' <span class="ok">✓ non-inferior</span>' if r["non_inferior"] else
                   ' <span class="bad">✗ judged inferior</span>')
        saved = r["baseline_cost"] - r["routed_cost"]
        badge = (f'<span class="badge switch">{e(r["routed_model"])}</span>' if r["switched"]
                 else f'<span class="badge">{e(r["routed_model"])} (no switch)</span>')
        blocks.append(f"""
  <details>
    <summary><b>{e(r['id'])}</b> · {e(r['category'])} · {badge} ·
      saved <b class="save">{usd(saved)}</b>{verdict}</summary>
    <p class="prompt">{e(r['prompt'][:1200])}</p>
    <div class="sxs">
      <div><h4>ModelPilot → {e(r['routed_model'])} · {usd(r['routed_cost'])}</h4>
        <pre>{e(r['routed_text'][:4000])}</pre></div>
      <div><h4>Baseline → {e(r['baseline_model'])} · {usd(r['baseline_cost'])}</h4>
        <pre>{e(r['baseline_text'][:4000])}</pre></div>
    </div>
  </details>""")

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>ModelPilot — side-by-side comparison</title>
<style>
  body {{ font: 14px/1.5 -apple-system, "Segoe UI", sans-serif; margin: 2rem auto;
         max-width: 960px; color: #1f2430; padding: 0 1rem; }}
  h1 {{ font-size: 1.4rem; }} .muted {{ color: #6b7080; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 1rem 0; }}
  .card {{ border: 1px solid #e3e3e8; border-radius: 8px; padding: 10px 14px; min-width: 160px; }}
  .card.hero {{ border-color: #bfe5cc; background: #f4fbf6; }}
  .num {{ font-size: 1.25rem; font-weight: 600; }} .label {{ color: #6b7080; font-size: 0.8rem; }}
  .save {{ color: #2e9e5b; }} .ok {{ color: #2e9e5b; }} .bad {{ color: #b3372f; }}
  .badge {{ background: #f6f7f9; border: 1px solid #e3e3e8; border-radius: 10px;
           padding: 1px 8px; font-size: 0.8rem; }}
  .badge.switch {{ background: #f0faf3; border-color: #d8efe0; }}
  details {{ border: 1px solid #eee; border-radius: 8px; margin: 8px 0; padding: 8px 12px; }}
  summary {{ cursor: pointer; }}
  .prompt {{ background: #f6f7f9; border-radius: 6px; padding: 8px 10px; font-size: 0.85rem; }}
  .sxs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .sxs h4 {{ margin: 6px 0; font-size: 0.85rem; }}
  pre {{ white-space: pre-wrap; background: #fbfbfc; border: 1px solid #eee; border-radius: 6px;
        padding: 8px; font-size: 0.8rem; max-height: 360px; overflow-y: auto; }}
</style></head><body>
<h1>ModelPilot side-by-side: routed vs all-{e(result['baseline'])}</h1>
<p class="muted">Same prompts, two arms. Generated {e(result['generated_at'])}.
Costs are actual tokens at list prices. Verdicts are pairwise, position-debiased
non-inferiority judgments of the routed output against the baseline output.</p>
{cards}
{''.join(blocks)}
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompts", help="jsonl with {'id','prompt'} rows; default: 20 from the seed corpus")
    parser.add_argument("--from-captures", action="store_true",
                        help="prove it on YOUR traffic: use prompts captured by the gateway "
                             "(needs MODELPILOT_CAPTURE_PCT>0 during a run)")
    parser.add_argument("--db", default="modelpilot.db", help="ledger db for --from-captures")
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--judge", action="store_true", help="add non-inferiority verdicts (extra API calls)")
    parser.add_argument("--offline", action="store_true", help="no API, synthetic outputs — report shape only")
    parser.add_argument("--save-to-db", action="store_true",
                        help="store the comparison so it renders inside the dashboard's proof panel")
    parser.add_argument("--out", default="compare_report.html")
    args = parser.parse_args()

    if args.from_captures:
        from .ledger import Ledger
        ledger = Ledger(args.db)
        caps = ledger.captures()
        ledger.close()
        if not caps:
            sys.exit("No captured prompts found. Run the gateway with "
                     "MODELPILOT_CAPTURE_PCT>0 for a while, then retry.")
        prompts = [{"id": c["request_id"][:8], "prompt": c["prompt"]} for c in caps[-args.n:]]
    elif args.prompts:
        with open(args.prompts) as f:
            prompts = [json.loads(line) for line in f if line.strip()]
    else:
        from .goldenset.seed_corpus import CORPUS
        prompts = [{"id": f"seed-{i:03d}", **row} for i, row in enumerate(CORPUS)]
        prompts = random.Random(11).sample(prompts, min(args.n, len(prompts)))

    if args.offline:
        run_fn, judge_fn = offline_run_fn, (offline_judge_fn if args.judge else None)
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            sys.exit("ANTHROPIC_API_KEY is not set. Set it, or use --offline.")
        run_fn = api_run_fn(api_key)
        judge_fn = api_judge_fn() if args.judge else None

    result = run_comparison(prompts, args.baseline, run_fn, judge_fn)
    with open(args.out, "w") as f:
        f.write(render_report(result))

    if args.save_to_db:
        from .ledger import Ledger
        ledger = Ledger(args.db)
        ledger.clear_proof()
        for row in result["rows"]:
            ledger.record_proof(row)
        ledger.close()
        print(f"saved {len(result['rows'])} rows to the dashboard proof panel ({args.db})")
    print(f"\nrouted {result['n_switched']}/{result['n']} prompts · "
          f"saved {result['savings_pct']:.0%} (${result['savings']:.2f})"
          + (f" · non-inferior {result['non_inferior_rate']:.0%}"
             if result["non_inferior_rate"] is not None else ""))
    print(f"report: {args.out}")


if __name__ == "__main__":
    main()
