from modelpilot.dashboard import collect_stats, render_html
from modelpilot.gateway import decide
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.router import recommend
from modelpilot.tune import build_policy

CLASSIFY = "Classify this review as positive or negative: 'terrible, broke in a day'"


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


# --- per-customer policy gates ---------------------------------------------

def test_category_gate_override_lets_a_route_through():
    # classification is high-confidence (~0.85). Global gate 0.9 blocks it...
    d = decide(_body(CLASSIFY), "autopilot", confidence_gate=0.9, holdout_pct=0.0)
    assert not d.applied
    # ...but a learned per-category gate of 0.8 lets it route.
    d2 = decide(_body(CLASSIFY), "autopilot", confidence_gate=0.9, holdout_pct=0.0,
                category_gates={"classification": 0.8})
    assert d2.applied and d2.routed_model == "claude-haiku-4-5"


def test_category_gate_override_can_block():
    d = decide(_body(CLASSIFY), "autopilot", confidence_gate=0.8, holdout_pct=0.0,
               category_gates={"classification": 0.99})
    assert not d.applied  # learned policy turned this category off


# --- continuous tuning ------------------------------------------------------

def _rec_for(prompt):
    return recommend(_body(prompt))


def test_build_policy_loosens_proven_safe_category(tmp_path):
    db = str(tmp_path / "t.db")
    ledger = Ledger(db)
    rec = _rec_for(CLASSIFY)
    for _ in range(25):  # clean volume, no incidents
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                      applied=True, status_code=200, usage=Usage(input_tokens=500, output_tokens=100))
    ledger.close()

    policy = build_policy(db, since_days=30)
    assert policy["category_gates"].get("classification") == 0.6  # AGGRESSIVE_GATE


def test_build_policy_blocks_category_with_incidents(tmp_path):
    db = str(tmp_path / "t.db")
    ledger = Ledger(db)
    rec = _rec_for(CLASSIFY)
    ids = []
    for _ in range(3):
        ids.append(ledger.record(mode="autopilot", recommendation=rec,
                                 routed_model=rec.recommended_model, applied=True,
                                 status_code=200, usage=Usage(input_tokens=500, output_tokens=100)))
    # two escalations (retries) pointing back at routed classification requests
    for orig in ids[:2]:
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.original_model,
                      applied=False, status_code=200, usage=Usage(input_tokens=500, output_tokens=100),
                      retry_of=orig)
    ledger.close()

    policy = build_policy(db, since_days=30)
    assert policy["category_gates"].get("classification") == 0.99  # BLOCK_GATE


def test_category_quality_counts(tmp_path):
    db = str(tmp_path / "t.db")
    ledger = Ledger(db)
    rec = _rec_for(CLASSIFY)
    oid = ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                        applied=True, status_code=200, usage=Usage(input_tokens=500, output_tokens=100))
    ledger.record_feedback(oid, "negative", "wrong tone")
    rows = {r["category"]: r for r in ledger.category_quality()}
    ledger.close()
    assert rows["classification"]["n_applied"] == 1
    assert rows["classification"]["n_negative"] == 1


# --- conversion panel -------------------------------------------------------

def _seed_switch_ledger(db):
    ledger = Ledger(db)
    rec = _rec_for(CLASSIFY)  # switch, confidence ~0.85
    for _ in range(3):
        ledger.record(mode="advise", recommendation=rec, routed_model=rec.original_model,
                      applied=False, status_code=200, usage=Usage(input_tokens=10_000, output_tokens=2_000))
    ledger.close()


def test_dashboard_panel_sells_switch_in_guidance(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELPILOT_MODE", "guidance")
    db = str(tmp_path / "d.db")
    _seed_switch_ledger(db)
    ledger = Ledger(db)
    html = render_html(collect_stats(ledger, days=1))
    ledger.close()
    assert "READY TO SWITCH TO AUTOPILOT" in html
    assert "guidance mode" in html
    assert "compare --from-captures" in html


def test_dashboard_embeds_side_by_side_proof(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELPILOT_MODE", "guidance")
    db = str(tmp_path / "d.db")
    ledger = Ledger(db)
    ledger.record_proof({
        "prompt": "Classify this ticket sentiment",
        "category": "classification",
        "routed_model": "claude-haiku-4-5",
        "baseline_model": "claude-opus-4-8",
        "routed_text": "ROUTED-OUTPUT-TEXT",
        "baseline_text": "STANDARD-OUTPUT-TEXT",
        "routed_cost": 0.001, "baseline_cost": 0.010, "non_inferior": True,
    })
    summ = ledger.proof_summary()
    ledger.close()
    assert summ["n"] == 1 and abs(summ["savings"] - 0.009) < 1e-9
    assert summ["non_inferior_rate"] == 1.0

    ledger = Ledger(db)
    html_out = render_html(collect_stats(ledger, days=1))
    ledger.close()
    # both columns and both outputs render inside the dashboard
    assert "ROUTED-OUTPUT-TEXT" in html_out and "STANDARD-OUTPUT-TEXT" in html_out
    assert "claude-haiku-4-5" in html_out and "non-inferior" in html_out


def test_dashboard_panel_reassures_in_autopilot(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELPILOT_MODE", "autopilot")
    db = str(tmp_path / "d.db")
    ledger = Ledger(db)
    rec = _rec_for(CLASSIFY)
    ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                  applied=True, status_code=200, usage=Usage(input_tokens=10_000, output_tokens=2_000))
    ledger.close()
    ledger = Ledger(db)
    html = render_html(collect_stats(ledger, days=1))
    ledger.close()
    assert "AUTOPILOT" in html and "saved" in html
