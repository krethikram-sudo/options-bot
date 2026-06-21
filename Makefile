# Outlay — convenience targets.
.PHONY: dogfood dogfood-full test help

help:
	@echo "make dogfood        Real-spend proof: cost YOUR OWN Claude Code usage,"
	@echo "                    cache-aware vs naive. No GitHub, no keys."
	@echo "make dogfood-full REPO=owner/name   Full self-attribution report (needs GITHUB_TOKEN)."
	@echo "make test           Run the outlay + console test suites."

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
