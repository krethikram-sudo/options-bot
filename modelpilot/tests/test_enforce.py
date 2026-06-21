"""Program hard-cap enforcement: local decision logic + the gateway block path."""

from fastapi.testclient import TestClient

from modelpilot import enforce


def test_decide_matches_block_downgrade_allow():
    block = [{"name": "Platform", "action": "block",
              "members": [{"scope_type": "project", "scope_id": "PLAT"}]}]
    # project key from the ticket → match
    assert enforce.decide(block, ticket="PLAT-912")["decision"] == "block"
    # unrelated ticket → allow
    assert enforce.decide(block, ticket="GROW-1")["decision"] == "allow"
    # team / work-type members need their own tag
    dg = [{"name": "Growth", "action": "downgrade", "floor_model": "claude-haiku-4-5",
           "members": [{"scope_type": "team", "scope_id": "growth"},
                       {"scope_type": "class", "scope_id": "feature"}]}]
    d = enforce.decide(dg, team="growth")
    assert d["decision"] == "downgrade" and d["floor_model"] == "claude-haiku-4-5"
    assert enforce.decide(dg, work_type="feature")["decision"] == "downgrade"
    assert enforce.decide(dg, team="other")["decision"] == "allow"
    # block wins when a call matches both a block and a downgrade program
    both = block + [{"name": "P2", "action": "downgrade",
                     "members": [{"scope_type": "project", "scope_id": "PLAT"}]}]
    assert enforce.decide(both, ticket="PLAT-1")["decision"] == "block"
    # empty / no match
    assert enforce.decide([], ticket="PLAT-1")["decision"] == "allow"


def test_fetch_enforced_fails_open():
    # no config → None (nothing enforced); unreachable console → None (keep cache)
    assert enforce.fetch_enforced(None, "k") is None
    assert enforce.fetch_enforced("http://127.0.0.1:1", "k", timeout=0.2) is None


def test_gateway_blocks_call_over_hard_cap(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELPILOT_DB", str(tmp_path / "enf.db"))
    monkeypatch.setenv("MODELPILOT_ENFORCE", "1")
    import importlib

    from modelpilot import gateway as gw
    importlib.reload(gw)
    try:
        with TestClient(gw.app) as client:
            # seed the cached verdict (the refresh loop is off without a console)
            gw.app.state.enforced = [{"id": 7, "name": "Platform", "action": "block",
                                      "members": [{"scope_type": "project", "scope_id": "PLAT"}]}]
            # a call tagged to PLAT is blocked (402) before any upstream call
            r = client.post("/v1/messages",
                            headers={"x-modelpilot-work-ticket": "PLAT-42"},
                            json={"model": "claude-opus-4-8", "max_tokens": 8,
                                  "messages": [{"role": "user", "content": "hi"}]})
            assert r.status_code == 402
            assert r.headers.get("x-modelpilot-enforced") == "block"
            assert r.headers.get("x-modelpilot-program") == "Platform"
            assert r.json()["error"]["type"] == "budget_exceeded"
            # the block is tallied for reporting back to the console
            assert gw.app.state.enforce_counts.get(7) == 1
    finally:
        importlib.reload(gw)
