#!/usr/bin/env bash
# Promote the ModelPilot source from the options-bot monorepo into the
# standalone github.com/krethikram-sudo/modelpilot repo as the new SOURCE OF
# TRUTH — full source, tests, tuning data, and internal docs (private).
#
# Run this from your Mac (you have push access to the modelpilot repo there;
# the cloud session does not). It assembles a clean standalone layout, proves
# it installs + tests green in a throwaway venv, then pushes to modelpilot:main.
#
# Layout produced in the modelpilot repo:
#   pyproject.toml  README.md  LICENSE  CHANGELOG.md  .gitignore
#   modelpilot/            <- the importable package (pip install -e . works)
#   tests/                 <- full test suite
#   goldenset_data/        <- calibration labels (CI regression test needs them)
#   internal/              <- strategy docs: NEVER invite customers to this repo
#   docs/TESTING.md        <- the prompt test matrix
#   scripts/ launchd/ site/ extension/ .github/
#
# Usage:
#   ./scripts/migrate_to_modelpilot.sh [modelpilot-git-url]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/modelpilot"
REMOTE="${1:-https://github.com/krethikram-sudo/modelpilot.git}"
WORK="$(mktemp -d -t modelpilot-migrate.XXXXXX)"
VENV="$(mktemp -d -t modelpilot-venv.XXXXXX)"
trap 'rm -rf "$VENV"' EXIT

echo "Source : $SRC"
echo "Target : $REMOTE"
echo "Staging: $WORK"

# --- clone target, base on its main so the push fast-forwards, empty worktree ---
git clone "$REMOTE" "$WORK"
cd "$WORK"
if git show-ref --verify --quiet refs/remotes/origin/main; then
  git checkout -q -B main origin/main
else
  git checkout -q -B main
fi
find "$WORK" -mindepth 1 -maxdepth 1 -not -name .git -exec rm -rf {} +

# --- importable package ---
mkdir -p "$WORK/modelpilot/goldenset"
cp "$SRC"/*.py "$WORK/modelpilot/"
cp "$SRC"/requirements.txt "$WORK/modelpilot/"
cp "$SRC"/goldenset/*.py "$WORK/modelpilot/goldenset/"

# --- tests ---
mkdir -p "$WORK/tests"
cp "$SRC"/tests/*.py "$WORK/tests/"

# --- root packaging (pyproject at root => editable install works) ---
cp "$SRC"/packaging/pyproject.toml "$SRC"/packaging/LICENSE \
   "$SRC"/packaging/CHANGELOG.md "$SRC"/packaging/README.md "$WORK/"

# --- golden-set tuning data (tracked: the calibration regression test reads it) ---
mkdir -p "$WORK/goldenset_data"
cp "$SRC"/goldenset_data/* "$WORK/goldenset_data/"

# --- internal strategy docs (PRIVATE — do not add customers as collaborators) ---
mkdir -p "$WORK/internal"
cp "$SRC"/PRODUCT_DESIGN.md "$SRC"/ROUTER_TUNING_PLAN.md "$SRC"/SAVINGS_DASHBOARD.md \
   "$SRC"/DEMO_SCRIPT.md "$SRC"/GTM_PLAN.md "$SRC"/COMPETITIVE.md \
   "$SRC"/PILOT_OUTREACH.md "$SRC"/pilot_tracker.csv "$WORK/internal/"
cp "$SRC"/README.md "$WORK/internal/PRODUCT_README.md"

# --- customer-facing test matrix ---
mkdir -p "$WORK/docs"
cp "$SRC"/CHAT_TEST_PROMPTS.md "$WORK/docs/TESTING.md"

# --- ancillary product surfaces ---
mkdir -p "$WORK/extension" "$WORK/scripts" "$WORK/launchd" "$WORK/site"
cp "$SRC"/extension/manifest.json "$SRC"/extension/background.js \
   "$SRC"/extension/content.js "$SRC"/extension/README.md "$WORK/extension/"
cp "$ROOT"/scripts/publish_modelpilot.sh "$ROOT"/scripts/install_modelpilot_gateway.sh "$WORK/scripts/"
cp "$ROOT"/launchd/com.modelpilot.gateway.plist.template "$WORK/launchd/"
cp "$SRC"/site/index.html "$WORK/site/"
cp -R "$SRC"/packaging/.github/ISSUE_TEMPLATE "$WORK/.github/ISSUE_TEMPLATE" 2>/dev/null || \
  { mkdir -p "$WORK/.github"; cp -R "$SRC"/packaging/.github/ISSUE_TEMPLATE "$WORK/.github/"; }

# NOTE: we deliberately do NOT push anything under .github/workflows/. GitHub
# rejects creating/updating ANY file there (any extension) unless the pushing
# token has the `workflow` scope — which neither the default Mac OAuth
# credential nor the publish PAT has. So we drop a ready-to-use CI config at
# docs/ci-workflow.yml; activate it after the migration from the GitHub web UI
# (create .github/workflows/ci.yml and paste it in — the web path needs no scope).
cat > "$WORK/docs/ci-workflow.yml" <<'EOF'
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: python -m pytest tests/ -q
EOF

# --- dev .gitignore (note: goldenset_data IS tracked here, unlike the publish) ---
cat > "$WORK/.gitignore" <<'EOF'
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
*.egg-info/
build/
dist/
modelpilot*.db
.env
EOF

# --- prove it installs + tests green before pushing ---
echo "Validating standalone layout in a throwaway venv..."
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q -e "$WORK[dev]"
"$VENV/bin/python" -m pytest "$WORK/tests" -q

# --- commit + push ---
cd "$WORK"
git config user.name  >/dev/null 2>&1 || git config user.name  "ModelPilot"
git config user.email >/dev/null 2>&1 || git config user.email "dev@modelpilot.local"
git add -A
if git diff --cached --quiet; then
  echo "Nothing to migrate — modelpilot already matches the source."
  exit 0
fi
git commit -q -m "Migrate full ModelPilot source of truth into the standalone repo

Package at root (editable install works), tests, golden-set calibration
data, product surfaces (site/extension/installer), and internal strategy
docs under internal/. This repo is now the development source of truth."
git push origin HEAD:main
echo
echo "Done. modelpilot is now the source of truth."
echo "Next on your Mac:"
echo "  git clone $REMOTE ~/modelpilot && cd ~/modelpilot"
echo "  python3 -m venv .venv && source .venv/bin/activate"
echo "  pip install -e \".[dev]\""
echo "  modelpilot gateway --mode autopilot --port 8410"
