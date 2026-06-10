from modelpilot.gateway import assign_arm, decide
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.report import _bootstrap_diff_ci
from modelpilot.router import recommend


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


CLASSIFY = "Classify this as positive or negative: 'meh'"


def test_arm_assignment_deterministic_and_proportional():
    arms = [assign_arm(f"session-{i}", 0.10) for i in range(2000)]
    assert arms == [assign_arm(f"session-{i}", 0.10) for i in range(2000)]  # stable
    control_share = arms.count("control") / len(arms)
    assert 0.06 < control_share < 0.14
    assert assign_arm("anything", 0.0) == "treatment"


def test_control_arm_never_applies():
    # Find a session key that lands in control at 100% holdout.
    d = decide(_body(CLASSIFY), "autopilot", confidence_gate=0.5,
               holdout_pct=1.0, session_key="s1")
    assert d.arm == "control"
    assert not d.applied
    assert d.routed_model == "claude-opus-4-8"
    assert d.recommendation.action == "switch"  # advice still logged


def test_treatment_arm_applies():
    d = decide(_body(CLASSIFY), "autopilot", confidence_gate=0.5,
               holdout_pct=0.0, session_key="s1")
    assert d.arm == "treatment"
    assert d.applied


def test_shadow_mode_is_observe_arm():
    d = decide(_body(CLASSIFY), "shadow", holdout_pct=1.0, session_key="s1")
    assert d.arm == "observe"


def test_feedback_and_escalation_accounting(tmp_path):
    ledger = Ledger(str(tmp_path / "t.db"))
    rec = recommend(_body(CLASSIFY))
    usage = Usage(input_tokens=10_000, output_tokens=2_000)

    rid = ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                        applied=True, status_code=200, usage=usage, arm="treatment")
    ledger.record_feedback(rid, "negative", "output missed the point")
    # The re-run on the original model, linked via retry_of.
    stay = recommend(_body("Refactor the billing module across multiple files."))
    ledger.record(mode="autopilot", recommendation=stay, routed_model=stay.original_model,
                  applied=False, status_code=200, usage=usage, arm="treatment", retry_of=rid)

    esc = ledger.escalation_costs()
    assert esc["n"] == 1
    assert esc["cost"] > 0

    guard = {g["arm"]: g for g in ledger.quality_guardrails()}
    assert guard["treatment"]["n_negative"] == 1
    ledger.close()


def test_arm_costs_split(tmp_path):
    ledger = Ledger(str(tmp_path / "t.db"))
    rec = recommend(_body(CLASSIFY))
    cheap = Usage(input_tokens=1_000, output_tokens=200)
    for i in range(3):
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                      applied=True, status_code=200, usage=cheap, arm="treatment")
    ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.original_model,
                  applied=False, status_code=200, usage=cheap, arm="control")
    arms = ledger.arm_costs()
    assert len(arms["treatment"]) == 3
    assert len(arms["control"]) == 1
    assert arms["control"][0] > arms["treatment"][0]  # opus row costs more
    ledger.close()


def test_bootstrap_ci_brackets_true_difference():
    a = [10.0 + (i % 5) * 0.1 for i in range(200)]   # mean ~10.2
    b = [8.0 + (i % 5) * 0.1 for i in range(200)]    # mean ~8.2
    lo, hi = _bootstrap_diff_ci(a, b)
    assert lo < 2.0 < hi or abs((lo + hi) / 2 - 2.0) < 0.1
    assert lo > 1.5 and hi < 2.5
