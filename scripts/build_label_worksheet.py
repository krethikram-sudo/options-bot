#!/usr/bin/env python3
"""Build a human-labeling worksheet for the golden set's OPEN-ENDED categories —
the ones where the current LLM-judge labels are least trustworthy
(CALIBRATION.md: "Do NOT lower the open-ended floors yet").

We do NOT fabricate human labels. This emits a CSV a human (founder or a labeler)
fills in: read the prompt, decide the cheapest model that is *actually good enough*,
and record it + a note. Re-import with apply_human_labels (below) to set
label_source=human on those rows so they're trusted differently from synthetic ones.

Usage:
  python scripts/build_label_worksheet.py            # -> label_worksheet.csv
  python scripts/build_label_worksheet.py --all      # every category, not just open-ended
  # ...human fills 'human_label' (+ optional 'note')...
  python scripts/build_label_worksheet.py --apply label_worksheet.csv   # write back
"""
import argparse
import csv
import json
import os
import sys

LABELS = os.path.join(os.path.dirname(__file__), "..", "modelpilot", "goldenset_data", "labels.jsonl")
VALID_MODELS = {"claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8", "claude-fable-5"}
# Where LLM-judge labels are weakest (open-ended generation/reasoning, small n).
OPEN_ENDED = {"math_logic", "analysis_strategy", "creative_longform", "conversation",
              "summarization_long", "codegen_complex", "debugging", "agentic"}


def _load():
    with open(LABELS) as f:
        return [json.loads(l) for l in f if l.strip()]


def build(out_path: str, every: bool):
    rows = _load()
    sel = [r for r in rows if every or r.get("category") in OPEN_ENDED]
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "current_label", "human_label", "note", "prompt"])
        for r in sel:
            w.writerow([r["id"], r.get("category", ""), r.get("label_model", ""), "", "",
                        r.get("prompt", "").replace("\n", "\\n")])
    print(f"wrote {len(sel)} rows to {out_path}")
    print("Fill 'human_label' with the cheapest model that is actually good enough "
          f"({', '.join(sorted(VALID_MODELS))}); leave blank to keep the current label.")


def apply(in_path: str):
    rows = _load()
    by_id = {r["id"]: r for r in rows}
    n = 0
    with open(in_path, newline="") as f:
        for rec in csv.DictReader(f):
            hl = (rec.get("human_label") or "").strip()
            if not hl:
                continue
            if hl not in VALID_MODELS:
                sys.exit(f"invalid human_label for {rec['id']}: {hl}")
            r = by_id.get(rec["id"])
            if not r:
                continue
            r["label_model"] = hl
            r["label_source"] = "human"
            if rec.get("note"):
                r["label_note"] = rec["note"]
            n += 1
    with open(LABELS, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"applied {n} human labels (label_source=human). Re-run the evaluator to "
          "re-measure against the trusted labels.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", metavar="CSV", help="write human labels back from a filled worksheet")
    ap.add_argument("--all", action="store_true", help="include every category, not just open-ended")
    ap.add_argument("-o", "--out", default="label_worksheet.csv")
    a = ap.parse_args()
    if a.apply:
        apply(a.apply)
    else:
        build(a.out, a.all)


if __name__ == "__main__":
    main()
