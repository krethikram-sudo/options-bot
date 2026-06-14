"""ModelPilot — model-routing cost optimizer for the Claude API.

Phase 0: drop-in gateway (shadow / advise / autopilot modes), heuristic router
with cache-aware economics, counterfactual savings ledger, and shadow report.
"""

# Versioning policy (enforced by CI version-guard + test_changelog_has_current_version):
#   INTEGER bump (0.x -> 1.0, 1.x -> 2.0): breaking changes — API/header/schema
#     changes, routing-behavior overhauls customers must re-validate against.
#   DECIMAL bump (0.1 -> 0.2): everything else that ships — features, router
#     retunes, fixes. Optional third digit for trivial patches.
# Every change to shipped code bumps this AND adds a CHANGELOG entry.
__version__ = "0.24.0"
