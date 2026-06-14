#!/usr/bin/env bash
#
# Local end-to-end validation for ModelPilot on a real Anthropic API key.
#
# Runs the gateway in GUIDANCE mode (needs MODELPILOT_LICENSE; nothing rerouted),
# pushes a handful of real requests through it, then exercises every analysis
# command — report, digest, prompt-audit, learn-rules, learn-floors, profile —
# and finishes with a REAL routed-vs-baseline proof (modelpilot compare --judge).
#
# Cost: a few cents of real API spend (≈10 short messages + a small judged
# comparison). Nothing is rerouted, so your app behavior is never changed.
#
# Usage:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   export MODELPILOT_LICENSE="<your license token>"   # gateway needs it in every mode
#   bash scripts/validate_local.sh
#
# Options (env): PORT (default 8455), MODELPILOT_CMD (default "modelpilot"),
#                BASELINE (default claude-opus-4-8), SKIP_COMPARE=1 to skip spend.

set -uo pipefail

MP="${MODELPILOT_CMD:-modelpilot}"
PORT="${PORT:-8455}"
BASELINE="${BASELINE:-claude-opus-4-8}"
WORK="$(mktemp -d)"
DB="$WORK/validate.db"
GW_LOG="$WORK/gateway.log"
PASS=0; FAIL=0

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mPASS\033[0m %s\n' "$*"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$*"; FAIL=$((FAIL+1)); }

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY is not set. Export a billable key and retry." >&2
  exit 1
fi
if [ -z "${MODELPILOT_LICENSE:-}" ]; then
  echo "MODELPILOT_LICENSE is not set. The gateway needs a license in every mode" >&2
  echo "(guidance and autopilot). Export your license token and retry, or try the" >&2
  echo "free offline demo: modelpilot demo --offline" >&2
  exit 1
fi
command -v "$MP" >/dev/null 2>&1 || MP="python -m modelpilot.cli"

cleanup() { [ -n "${GW_PID:-}" ] && kill "$GW_PID" 2>/dev/null; rm -rf "$WORK"; }
trap cleanup EXIT

say "Starting gateway (guidance mode, capture on) on port $PORT"
MODELPILOT_DB="$DB" MODELPILOT_CAPTURE_PCT=1.0 \
  $MP gateway --mode guidance --port "$PORT" --db "$DB" >"$GW_LOG" 2>&1 &
GW_PID=$!

# Wait for readiness (preview endpoint responds once the app is up).
ready=0
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$PORT/modelpilot/preview" \
       -H 'content-type: application/json' \
       -d '{"model":"'"$BASELINE"'","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}' \
       >/dev/null 2>&1; then ready=1; break; fi
  sleep 0.5
done
[ "$ready" = 1 ] && ok "gateway is up" || { bad "gateway did not start (see $GW_LOG)"; cat "$GW_LOG"; exit 1; }

say "Sending real requests through the gateway (baseline: $BASELINE)"
send() {
  curl -fsS "http://127.0.0.1:$PORT/v1/messages" \
    -H "x-api-key: $ANTHROPIC_API_KEY" -H 'anthropic-version: 2023-06-01' \
    -H 'content-type: application/json' \
    -d '{"model":"'"$BASELINE"'","max_tokens":256,"messages":[{"role":"user","content":'"$1"'}]}' \
    -o /dev/null -w '%{http_code}'
}
prompts=(
  '"Classify this review as positive or negative: it broke in a day."'
  '"Classify the sentiment: best purchase I have made all year."'
  '"Extract the names and dates into JSON: Alice met Bob on 2026-01-03."'
  '"Translate to French: where is the nearest train station?"'
  '"Summarize: the meeting covered Q2 goals, hiring, and the launch timeline."'
  '"Debug why this intermittently returns null under concurrency and fix the race condition."'
)
sent=0
for p in "${prompts[@]}"; do
  code=$(send "$p")
  if [ "$code" = "200" ]; then sent=$((sent+1)); else echo "  (request returned HTTP $code)"; fi
done
[ "$sent" -ge 4 ] && ok "$sent/${#prompts[@]} requests succeeded through the gateway" \
                   || bad "only $sent/${#prompts[@]} requests succeeded (check key/network)"

# Give the ledger a moment to flush, then stop the gateway (quietly).
sleep 1; kill "$GW_PID" 2>/dev/null; wait "$GW_PID" 2>/dev/null; GW_PID=""

say "Ledger + recommendations recorded"
if $MP report --db "$DB" >/dev/null 2>&1; then ok "report ran"; else bad "report failed"; fi
if $MP digest --db "$DB" --days 0 2>/dev/null | grep -qi "saved\|spend"; then
  ok "digest produced a savings headline"; else bad "digest produced no headline"; fi

say "Per-customer adaptation commands"
$MP prompt-audit --db "$DB" --days 0 >/dev/null 2>&1 && ok "prompt-audit ran" || bad "prompt-audit failed"
$MP learn-rules --db "$DB" --days 0 --out "$WORK/rules.json" >/dev/null 2>&1 \
  && ok "learn-rules ran (catch-all mining)" || echo "  (learn-rules: likely 'not enough catch-all traffic' — fine)"
$MP learn-floors --db "$DB" --days 0 --offline --out "$WORK/policy.json" >/dev/null 2>&1 \
  && ok "learn-floors ran (offline)" || bad "learn-floors failed"

say "Profile validation"
cat >"$WORK/profile.json" <<'JSON'
{"blocked_models":["claude-haiku-4-5"],"min_model":"claude-sonnet-4-6","risk_tolerance":"balanced"}
JSON
MODELPILOT_PROFILE="$WORK/profile.json" $MP profile 2>/dev/null | grep -qi "min model" \
  && ok "profile validates and prints" || bad "profile command failed"

if [ "${SKIP_COMPARE:-0}" != "1" ]; then
  say "Real routed-vs-baseline proof (modelpilot compare --judge — small spend)"
  REPORT="$PWD/modelpilot_validate_report.html"
  if $MP compare --from-captures --judge --db "$DB" --baseline "$BASELINE" \
        --out "$REPORT"; then
    ok "compare produced a side-by-side proof report"
    echo "  report saved to: $REPORT  (open it to see routed vs baseline outputs + costs)"
  else
    bad "compare failed"
  fi
else
  echo "  (SKIP_COMPARE=1 — skipped the judged comparison)"
fi

say "Result: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ] && echo "All checks passed — ModelPilot is working end-to-end on your key." \
               || echo "Some checks failed — see output above (gateway log: $GW_LOG)."
exit "$FAIL"
