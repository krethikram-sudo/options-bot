from modelpilot.digest import build_digest, render_markdown, render_slack
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.router import recommend

CLASSIFY = "Classify this review as positive or negative: 'terrible, broke in a day'"


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


def test_digest_shadow_reports_potential(tmp_path):
    db = str(tmp_path / "d.db")
    ledger = Ledger(db)
    usage = Usage(input_tokens=10_000, output_tokens=2_000)
    rec = recommend(_body(CLASSIFY))
    for _ in range(3):
        ledger.record(mode="shadow", recommendation=rec, routed_model=rec.original_model,
                      applied=False, status_code=200, usage=usage)
    ledger.close()

    d = build_digest(db, days=7)
    assert d["routing_live"] is False
    # classification is high-confidence (0.85 >= 0.8 gate), so the gated headline
    # equals the raw potential here.
    assert d["headline_saved"] == d["gated_potential"] == d["potential"] > 0
    assert d["requests"] == 3
    md = render_markdown(d)
    assert "Could have saved" in md
    assert d["top_categories"][0]["category"] == rec.category


def test_digest_gated_potential_excludes_low_confidence(tmp_path):
    db = str(tmp_path / "d.db")
    ledger = Ledger(db)
    usage = Usage(input_tokens=10_000, output_tokens=2_000)
    rec = recommend(_body("Help me plan my week."))  # conversation, low confidence
    assert rec.action == "switch" and rec.confidence < 0.8
    for _ in range(3):
        ledger.record(mode="shadow", recommendation=rec, routed_model=rec.original_model,
                      applied=False, status_code=200, usage=usage)
    ledger.close()

    d = build_digest(db, days=7)  # default gate 0.8
    assert d["potential"] > 0            # raw recommendations exist
    assert d["gated_potential"] == 0     # but none clear the gate
    assert d["headline_saved"] == 0      # so shadow doesn't oversell


def test_digest_autopilot_reports_net_realized(tmp_path):
    db = str(tmp_path / "d.db")
    ledger = Ledger(db)
    usage = Usage(input_tokens=10_000, output_tokens=2_000)
    rec = recommend(_body(CLASSIFY))
    for _ in range(4):
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                      applied=True, status_code=200, usage=usage)
    ledger.close()

    d = build_digest(db, days=7)
    assert d["routing_live"] is True
    assert d["headline_saved"] == d["net_realized"] > 0
    assert d["applied"] == 4
    assert "Saved" in render_markdown(d)


def test_digest_slack_payload_is_text(tmp_path):
    db = str(tmp_path / "d.db")
    ledger = Ledger(db)
    ledger.record(mode="shadow", recommendation=recommend(_body(CLASSIFY)),
                  routed_model="claude-opus-4-8", applied=False, status_code=200,
                  usage=Usage(input_tokens=5_000, output_tokens=1_000))
    ledger.close()

    payload = render_slack(build_digest(db, days=7))
    assert "text" in payload and "ModelPilot" in payload["text"]


def test_errored_requests_excluded_from_summary(tmp_path):
    db = str(tmp_path / "e.db")
    ledger = Ledger(db)
    rec = recommend(_body(CLASSIFY))
    ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                  applied=True, status_code=200, usage=Usage(input_tokens=5_000, output_tokens=1_000))
    ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                  applied=True, status_code=401, usage=Usage())
    s = ledger.summary()
    ledger.close()
    assert s["n"] == 1  # only the successful request counts


def test_digest_quality_warming_up_without_holdout(tmp_path):
    db = str(tmp_path / "d.db")
    ledger = Ledger(db)
    ledger.record(mode="shadow", recommendation=recommend(_body(CLASSIFY)),
                  routed_model="claude-opus-4-8", applied=False, status_code=200,
                  usage=Usage(input_tokens=5_000, output_tokens=1_000))
    ledger.close()

    d = build_digest(db, days=7)
    assert d["quality"]["status"] == "warming_up"
