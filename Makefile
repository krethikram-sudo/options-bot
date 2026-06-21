# Outlay — convenience targets.
.PHONY: dogfood dogfood-full test deploy help

CONSOLE_APP ?= modelpilot-console-prod

help:
	@echo "make dogfood        Real-spend proof: cost YOUR OWN Claude Code usage,"
	@echo "                    cache-aware vs naive. No GitHub, no keys."
	@echo "make dogfood-full REPO=owner/name   Full self-attribution report (needs GITHUB_TOKEN)."
	@echo "make test           Run the outlay + console test suites."
	@echo "make deploy         Deploy the console to Fly (app=\$$CONSOLE_APP, default $(CONSOLE_APP))."

# Real-spend proof for the demo — costs your local Claude Code transcripts
# (~/.claude/projects) the cache-aware way and shows the naive-tracker inflation.
# This is the honest 'we run it on ourselves' number; no tracker/keys required.
dogfood:
	@python -m outlay.dogfood --proof-only

# Full self-attribution report against a repo you own. Pulls the repo's issues
# (read-only) and attributes your Claude Code spend to them.
#   GITHUB_TOKEN=… make dogfood-full REPO=owner/name
dogfood-full:
	@python -m outlay.dogfood --repo "$(REPO)"

test:
	@python -m pytest outlay/tests/ console/test_console.py -q

# Build + ship the console image to Fly (builds console/Dockerfile from the repo
# root). Works from a Mac with `fly auth login`, or from a cloud session once
# FLY_API_TOKEN + flyctl + the Fly network allowlist are configured
# (see docs/DEPLOY_FROM_CLOUD.md). Override the app with: make deploy CONSOLE_APP=name
deploy:
	@command -v fly >/dev/null 2>&1 || { echo "flyctl not found — see docs/DEPLOY_FROM_CLOUD.md"; exit 1; }
	fly deploy -a $(CONSOLE_APP)
