#!/usr/bin/env bash
# Build the PUBLISHABLE thin client (modelpilot-client) from the monorepo.
#
# The thin client is the only half of the split architecture that is safe to put
# on PyPI: it classifies locally (commodity lexical heuristics) and asks a hosted
# brain for the actual routing decision. It must NOT carry the routing IP — the
# price table, per-category capability floors, switch economics, calibration, or
# the ledger/dashboard. This script copies only the publishable closure and then
# HARD-FAILS if anything IP-bearing leaked in.
#
# Usage:  scripts/build_client.sh [outdir]   (default: dist/modelpilot-client)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/dist/modelpilot-client}"
PKG="$OUT/modelpilot"

# The publishable closure: commodity classifier + brain client + thin proxy.
# (router_classify imports only stdlib; brain_client + client_proxy import only
# router_classify + brain_client + fastapi/httpx/uvicorn.)
PUBLISHABLE=(router_classify.py brain_client.py client_proxy.py sdk.py retry.py cache.py)

# Modules that must NEVER ship in the client (the IP) — used for the leak audit.
FORBIDDEN_MODULES=(pricing taxonomy gateway floorlearn profile rules promptsavings \
                   telemetry compare bedrock ledger replay tune digest demo report)
# Symbols that would betray the economics/floor IP even if copy-pasted inline.
FORBIDDEN_SYMBOLS=("CAPABILITY_LADDER" "net_switch_benefit" "PRICES" "CATEGORIES =" \
                   "ModelPrice" "cache_switch_penalty" "request_cost")

echo "==> staging $OUT"
rm -rf "$OUT"
mkdir -p "$PKG"

# __version__ comes from the monorepo so client + brain stay in lockstep.
VERSION="$(python -c "import re,pathlib;print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('$ROOT/modelpilot/__init__.py').read_text()).group(1))")"
cat > "$PKG/__init__.py" <<EOF
"""ModelPilot thin client — drop-in Claude API proxy that routes via a hosted
ModelPilot brain. Carries no routing IP; the brain holds floors + economics."""

__version__ = "$VERSION"

from .sdk import anthropic_client, async_anthropic_client, proxy_url  # noqa: F401
EOF

for f in "${PUBLISHABLE[@]}"; do
  cp "$ROOT/modelpilot/$f" "$PKG/$f"
  echo "    + modelpilot/$f"
done

cp "$ROOT/modelpilot/packaging/LICENSE" "$OUT/LICENSE" 2>/dev/null || true

cat > "$OUT/pyproject.toml" <<EOF
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "modelpilot-client"
version = "$VERSION"
description = "Drop-in Claude API proxy that routes each request via a hosted ModelPilot brain to cut spend — IP stays server-side."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "Proprietary" }
authors = [{ name = "ModelPilot", email = "krethikram@gmail.com" }]
dependencies = ["fastapi>=0.110", "uvicorn>=0.27", "httpx>=0.26"]

[project.scripts]
modelpilot-client = "modelpilot.client_proxy:main"

[tool.setuptools]
packages = ["modelpilot"]
EOF

cat > "$OUT/README.md" <<'EOF'
# ModelPilot thin client

Drop-in proxy for the Claude Messages API. Point your app at it; it classifies
each request locally and asks a hosted ModelPilot **brain** whether to route the
request to a cheaper model. Only a task category + numeric features ever leave
the box — never prompt text, model outputs, or your API key. If the brain is
unreachable it **fails open**: traffic is forwarded unchanged.

```bash
pip install modelpilot-client
export MODELPILOT_BRAIN_URL=https://your-brain.example.com
export MODELPILOT_LICENSE=...            # optional; the 7-day trial is server-tracked
modelpilot-client                        # listens on :8400, proxies to api.anthropic.com
# then point your SDK at http://127.0.0.1:8400
```

Environment: `MODELPILOT_BRAIN_URL`, `MODELPILOT_MODE` (autopilot|advise|shadow),
`MODELPILOT_UPSTREAM`, `MODELPILOT_LICENSE`, `MODELPILOT_PORT`, `MODELPILOT_DB`.

This package contains no pricing, capability-floor, or routing-economics logic —
that lives in the brain. Questions: krethikram@gmail.com
EOF

echo "==> auditing for IP leaks"
fail=0
for mod in "${FORBIDDEN_MODULES[@]}"; do
  if grep -REn "(from[[:space:]]+\.${mod}[[:space:]]+import|from[[:space:]]+modelpilot\.${mod}[[:space:]]+import|import[[:space:]]+modelpilot\.${mod}\b|from[[:space:]]+\.[[:space:]]+import[[:space:]].*\b${mod}\b)" "$PKG" >/dev/null 2>&1; then
    echo "  !! LEAK: client imports forbidden module '$mod'"; grep -REn "${mod}" "$PKG" || true; fail=1
  fi
done
for sym in "${FORBIDDEN_SYMBOLS[@]}"; do
  if grep -REn -- "$sym" "$PKG" >/dev/null 2>&1; then
    echo "  !! LEAK: client contains forbidden symbol '$sym'"; fail=1
  fi
done

# Import the staged client in isolation: it must load with ONLY its declared
# deps present and must not transitively pull in pricing/taxonomy/router.
echo "==> import-isolation check"
python - "$OUT" <<'PY'
import importlib.util, pathlib, sys
out = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(out))
# Drop the monorepo so a stray `from .router import` can't be satisfied.
sys.path = [p for p in sys.path if pathlib.Path(p or ".").resolve() != pathlib.Path.cwd().resolve()]
import modelpilot.router_classify as rc
import modelpilot.brain_client as bc
import modelpilot.client_proxy as cp  # noqa: F401
for banned in ("modelpilot.pricing", "modelpilot.taxonomy", "modelpilot.router", "modelpilot.gateway"):
    assert banned not in sys.modules, f"LEAK: {banned} got imported by the client"
# Functional smoke: commodity classify works and returns no tier.
f = rc.extract_features({"model": "claude-opus-4-8", "max_tokens": 16,
                         "messages": [{"role": "user", "content": "Classify this as spam or not."}]})
cat, tier, conf, _ = rc.classify(f)
assert tier is None and cat == "classification", (cat, tier)
print(f"    ok — client imports clean; classify -> {cat} (conf {conf}, tier {tier})")
PY

if [ "$fail" -ne 0 ]; then
  echo "==> FAILED: IP leak detected — not publishable."; exit 1
fi
echo "==> OK: $OUT (modelpilot-client $VERSION) is publishable."
echo "    build:   python -m build \"$OUT\""
