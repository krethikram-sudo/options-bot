#!/usr/bin/env bash
# Assemble the standalone, customer-shareable ModelPilot repo from this
# monorepo and (optionally) push it to a GitHub remote.
#
# SHIP list is an explicit allowlist: internal strategy docs (PRODUCT_DESIGN,
# ROUTER_TUNING_PLAN, PILOT_OUTREACH, DEMO_SCRIPT, CALIBRATION, golden-set
# data) are excluded by construction, not by remembering to exclude them.
#
# Usage:
#   ./scripts/publish_modelpilot.sh /tmp/modelpilot-beta
#   ./scripts/publish_modelpilot.sh /tmp/modelpilot-beta git@github.com:krethikram-sudo/modelpilot.git
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/modelpilot"
DEST="${1:?usage: publish_modelpilot.sh <dest-dir> [remote-url]}"
REMOTE="${2:-}"

if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null | grep -v '^\.git$' || true)" ]; then
    echo "ERROR: $DEST exists and is not empty (a .git dir alone is fine for re-publish)" >&2
    exit 1
fi

echo "Assembling beta repo in $DEST"
mkdir -p "$DEST/modelpilot/goldenset" "$DEST/tests" "$DEST/extension" \
         "$DEST/scripts" "$DEST/launchd" "$DEST/docs" "$DEST/site"

# --- package code ---
cp "$SRC"/__init__.py "$SRC"/cli.py "$SRC"/gateway.py "$SRC"/router.py \
   "$SRC"/pricing.py "$SRC"/taxonomy.py "$SRC"/ledger.py "$SRC"/dashboard.py \
   "$SRC"/chat.py "$SRC"/continuation.py "$SRC"/demo.py "$SRC"/report.py \
   "$SRC"/compare.py "$SRC"/replay.py "$SRC"/digest.py "$SRC"/tune.py "$SRC"/license.py \
   "$SRC"/requirements.txt "$DEST/modelpilot/"
# Public license key (safe to ship): present once `license keygen` has been run.
[ -f "$SRC/license_pubkey.pem" ] && cp "$SRC/license_pubkey.pem" "$DEST/modelpilot/"

# --- landing page (GitHub Pages deploys from site/ via pages.yml) ---
cp "$SRC"/site/index.html "$DEST/site/"
cp "$SRC"/goldenset/*.py "$DEST/modelpilot/goldenset/"

# --- tests (ship them: beta users and CI both benefit) ---
cp "$SRC"/tests/*.py "$DEST/tests/"

# --- browser extension ---
cp "$SRC"/extension/manifest.json "$SRC"/extension/background.js \
   "$SRC"/extension/content.js "$SRC"/extension/README.md "$DEST/extension/"

# --- macOS installer ---
cp "$ROOT/scripts/install_modelpilot_gateway.sh" "$DEST/scripts/"
cp "$ROOT/launchd/com.modelpilot.gateway.plist.template" "$DEST/launchd/"
chmod +x "$DEST/scripts/install_modelpilot_gateway.sh"

# --- customer docs ---
cp "$SRC/CHAT_TEST_PROMPTS.md" "$DEST/docs/TESTING.md"

# --- repo root: packaging (README, pyproject, LICENSE, CHANGELOG) ---
cp "$SRC/packaging/README.md" "$SRC/packaging/pyproject.toml" \
   "$SRC/packaging/LICENSE" "$SRC/packaging/CHANGELOG.md" "$DEST/"
# Ship issue templates (customer feedback channel) but NOT .github/workflows:
# pushing workflow files needs a `workflow`-scoped token, and they add nothing
# to the beta — Pages can't run on a private repo, and the build is already
# tested in-place above before it's committed, so customer-side CI is redundant.
mkdir -p "$DEST/.github"
cp -R "$SRC/packaging/.github/ISSUE_TEMPLATE" "$DEST/.github/"

cat > "$DEST/.gitignore" <<'EOF'
__pycache__/
*.pyc
.pytest_cache/
venv/
*.egg-info/
build/
dist/
modelpilot*.db
goldenset_data/
.env
license_private_key.pem
EOF

# --- sanity: build must be importable and green before it can ship ---
echo "Running test suite against the assembled repo..."
( cd "$DEST" && python3 -m pytest tests/ -q )

# --- git ---
cd "$DEST"
if [ ! -d .git ]; then
    git init -q -b main
fi
# Publishing must work in bare environments (CI runners, fresh containers):
# provide an identity if none exists and never require commit signing here.
git config user.name >/dev/null 2>&1 || git config user.name "ModelPilot Publisher"
git config user.email >/dev/null 2>&1 || git config user.email "publish@modelpilot.local"
git config commit.gpgsign false
git add -A
if ! git diff --cached --quiet; then
    git commit -q -m "ModelPilot beta $(python3 -c 'import modelpilot; print(modelpilot.__version__)' 2>/dev/null || echo 0.1.0)"
    echo "Committed."
else
    echo "No changes since last publish."
fi

if [ -n "$REMOTE" ]; then
    git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REMOTE"
    git push -u origin main
    echo "Pushed to $REMOTE"
else
    cat <<'EOF'

Next steps:
  1. Create a PRIVATE repo on GitHub (e.g. github.com/krethikram-sudo/modelpilot)
     — keep it private for the beta; invite customers as collaborators.
  2. Re-run with the remote:
       ./scripts/publish_modelpilot.sh <dest-dir> git@github.com:krethikram-sudo/modelpilot.git
  3. Edit the install URL in README.md (krethikram-sudo placeholder), commit, push.
EOF
fi
