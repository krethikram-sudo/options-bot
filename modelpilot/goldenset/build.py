"""Golden-set pipeline CLI.

  python -m modelpilot.goldenset.build submit  --workdir gs/   # prompts.jsonl -> batch
  python -m modelpilot.goldenset.build collect --workdir gs/   # batch -> outputs.jsonl
  python -m modelpilot.goldenset.build judge   --workdir gs/   # outputs -> judgments.jsonl
  python -m modelpilot.goldenset.build label   --workdir gs/   # judgments -> labels.jsonl

The submit/collect split exists because batches can take up to an hour.
Requires ANTHROPIC_API_KEY (or an `ant auth login` profile).
"""

import argparse
import os
from collections import defaultdict

from . import fanout, judge, label as labeling

BASELINE = os.environ.get("MODELPILOT_BASELINE", "claude-opus-4-8")


def _client():
    import anthropic

    return anthropic.Anthropic()


def cmd_submit(workdir: str):
    prompts = fanout.load_jsonl(f"{workdir}/prompts.jsonl")
    batch_id = fanout.submit(_client(), prompts)
    with open(f"{workdir}/batch_id.txt", "w") as f:
        f.write(batch_id)
    print(f"submitted batch {batch_id} ({len(prompts)} prompts x {len(fanout.CANDIDATE_MODELS)} models)")


def cmd_collect(workdir: str):
    batch_id = open(f"{workdir}/batch_id.txt").read().strip()
    rows = fanout.collect(_client(), batch_id)
    fanout.dump_jsonl(rows, f"{workdir}/outputs.jsonl")
    errors = sum(1 for r in rows if "error" in r)
    print(f"collected {len(rows)} outputs ({errors} errors) -> outputs.jsonl")


def cmd_judge(workdir: str):
    prompts = {p["id"]: p for p in fanout.load_jsonl(f"{workdir}/prompts.jsonl")}
    outputs = defaultdict(dict)
    for row in fanout.load_jsonl(f"{workdir}/outputs.jsonl"):
        outputs[row["prompt_id"]][row["model"]] = row.get("text")
    client = _client()
    rows = []
    for prompt_id, by_model in outputs.items():
        verdicts = judge.judge_prompt(client, prompts[prompt_id], by_model, BASELINE)
        rows.append({"prompt_id": prompt_id, "verdicts": verdicts})
    fanout.dump_jsonl(rows, f"{workdir}/judgments.jsonl")
    print(f"judged {len(rows)} prompts -> judgments.jsonl")


def cmd_label(workdir: str):
    prompts = {p["id"]: p for p in fanout.load_jsonl(f"{workdir}/prompts.jsonl")}
    rows, dropped = [], 0
    for row in fanout.load_jsonl(f"{workdir}/judgments.jsonl"):
        chosen = labeling.label_from_verdicts(row["verdicts"], BASELINE)
        if chosen is None:
            dropped += 1
            continue
        p = prompts[row["prompt_id"]]
        rows.append({
            "id": row["prompt_id"],
            "prompt": p["prompt"],
            "category": p.get("category"),
            "label_model": chosen,
        })
    fanout.dump_jsonl(rows, f"{workdir}/labels.jsonl")
    print(f"labeled {len(rows)} prompts ({dropped} dropped) -> labels.jsonl")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["submit", "collect", "judge", "label"])
    parser.add_argument("--workdir", default="goldenset_data")
    args = parser.parse_args()
    {"submit": cmd_submit, "collect": cmd_collect, "judge": cmd_judge, "label": cmd_label}[args.command](args.workdir)


if __name__ == "__main__":
    main()
