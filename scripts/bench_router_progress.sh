#!/usr/bin/env bash
#
# Router progress benchmark — replays each router-affecting version over the
# SAME (current) golden-label set via git worktrees, so the only thing that
# varies is the router code. Answers "how much did each iteration improve" with
# coverage / accuracy / false-downgrade at the calibrated gate (0.6).
#
#   bash scripts/bench_router_progress.sh
#
# Holding the labels fixed is the whole point: it isolates routing quality from
# changes to the dataset. Per-customer iterations (rules/floors/profile) and
# recall additions that target traffic NOT in the static golden set won't move
# these numbers — those are measured longitudinally on real traffic instead.

set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
LABELS="$ROOT/modelpilot/goldenset_data/labels.jsonl"
BENCH="$ROOT/scripts/router_progress.py"
WT_BASE="$(mktemp -d)"
trap 'git worktree prune 2>/dev/null; rm -rf "$WT_BASE"' EXIT

# version label : git ref  (oldest -> newest)
REFS=(
  "0.1.0 router-v0:436ac08"
  "session-context:fa3ca92"
  "0.2.0 content-difficulty:cd1bffc"
  "0.3.2 recall+honest:6f5348a"
  "0.6.0 structured-guard:8373b36"
  "0.9.0 universal-guard:6aa00f4"
  "current HEAD:HEAD"
)

printf '%-28s %5s %9s %9s %8s | %s\n' "version" "n" "cov@.6" "acc@.6" "fdr@.6" "safe-gate (cov/fdr)"
printf -- '---------------------------------------------------------------------------------------\n'
for entry in "${REFS[@]}"; do
  label="${entry%%:*}"; ref="${entry##*:}"
  wt="$WT_BASE/$ref"
  git worktree add -q --detach "$wt" "$ref" 2>/dev/null || { printf '%-28s  (worktree failed)\n' "$label"; continue; }
  out=$(cd "$wt" && PYTHONPATH="$wt" python "$BENCH" --labels "$LABELS" 2>/dev/null)
  python3 - "$label" "$out" <<'PY'
import json, sys
label, raw = sys.argv[1], sys.argv[2]
try: d = json.loads(raw)
except Exception: print(f"{label:<28}  (no output)"); sys.exit()
if "error" in d: print(f"{label:<28}  ERROR {d['error']}"); sys.exit()
a, sg = d["at_0.6"], d["safe_gate"]
sgs = f"gate {sg['gate']:.2f}: {sg['coverage']:.1%}/{sg['fdr']:.1%}" if sg else "none (unsafe)"
print(f"{label:<28} {d['n']:>5} {a['coverage']:>8.1%} {a['accuracy']:>8.1%} {a['fdr']:>7.1%} | {sgs}")
PY
  git worktree remove --force "$wt" 2>/dev/null
done
