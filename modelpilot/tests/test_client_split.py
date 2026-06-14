"""Guard the split architecture's publishable boundary.

The thin client (router_classify + brain_client + client_proxy) is the only part
we put on PyPI. It must classify locally but carry NONE of the routing IP — no
price table, capability floors, or switch economics. These tests fail loudly if
a future change pulls the IP back into the client's import closure.
"""

import ast
import pathlib

import modelpilot.router_classify as rc
from modelpilot.router import classify as tier_classify

PKG = pathlib.Path(__file__).resolve().parent.parent
PUBLISHABLE = ["router_classify.py", "brain_client.py", "client_proxy.py"]
FORBIDDEN = {"pricing", "taxonomy", "router", "gateway", "ledger", "floorlearn",
             "profile", "rules", "promptsavings", "telemetry", "compare", "bedrock"}


def _local_imports(path: pathlib.Path) -> set[str]:
    """Same-package modules imported by `path` (e.g. `from .pricing import` ->
    'pricing', `from . import brain_client` -> 'brain_client')."""
    tree = ast.parse(path.read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level >= 1:
            if node.module:
                mods.add(node.module.split(".")[0])
            else:  # from . import X
                mods.update(a.name.split(".")[0] for a in node.names)
    return mods


def test_router_classify_pulls_in_no_ip():
    assert _local_imports(PKG / "router_classify.py") == set()


def test_publishable_closure_has_no_forbidden_imports():
    seen = set()
    for fname in PUBLISHABLE:
        local = _local_imports(PKG / fname)
        leaked = local & FORBIDDEN
        assert not leaked, f"{fname} imports IP-bearing modules: {leaked}"
        seen |= local
    # The whole closure only ever references its own publishable members.
    allowed = {f[:-3] for f in PUBLISHABLE} | {"__init__"}
    assert seen <= allowed, f"closure references unexpected local modules: {seen - allowed}"


def test_commodity_classify_returns_no_tier():
    feats = rc.extract_features({"model": "claude-opus-4-8", "max_tokens": 16,
                                 "messages": [{"role": "user", "content": "Classify this as spam or not."}]})
    category, tier, conf, _ = rc.classify(feats)  # no floor_tier -> commodity mode
    assert category == "classification" and tier is None and conf >= 0.8


def test_tier_mode_matches_commodity_category():
    # router.classify (tier-aware) and the commodity classifier agree on the
    # category — the split only adds the floor/economics layer, never changes
    # what the lexical classifier decides.
    body = {"model": "claude-opus-4-8", "max_tokens": 16,
            "messages": [{"role": "user", "content": "Extract all emails as JSON."}]}
    feats = rc.extract_features(body)
    commodity_cat, commodity_tier, *_ = rc.classify(feats)
    tier_cat, tier_tier, *_ = tier_classify(feats)
    assert commodity_cat == tier_cat == "extraction"
    assert commodity_tier is None and tier_tier == 0  # floor applied only tier-side


def test_commodity_followup_detected_without_floors():
    sess = {"model": "claude-opus-4-8", "max_tokens": 16, "messages": [
        {"role": "user", "content": "Debug why my job intermittently fails with a deadlock."},
        {"role": "assistant", "content": "It is a lock-ordering deadlock."},
        {"role": "user", "content": "why?"}]}
    feats = rc.extract_features(sess)
    category, tier, conf, _ = rc.classify(feats)
    assert category == "followup_in_context" and tier is None
