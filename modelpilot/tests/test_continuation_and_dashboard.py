from modelpilot.continuation import ContinuationModel
from modelpilot.dashboard import collect_stats, render_html
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.router import recommend


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


CLASSIFY = "Classify this as positive or negative: 'fine'"


class FakeLedger:
    def __init__(self, lengths):
        self._lengths = lengths

    def session_lengths(self, *a, **k):
        return self._lengths


def test_continuation_falls_back_when_sparse():
    model = ContinuationModel(FakeLedger([3, 4, 5]), default_remaining=7.0)
    assert model.expected_remaining(1) == 7.0


def test_continuation_mean_residual_life():
    # 100 sessions: half end at 2 turns, half at 10.
    lengths = [2] * 50 + [10] * 50
    model = ContinuationModel(FakeLedger(lengths))
    # At turn 1 every session survives: E[L-1] = mean(L) - 1 = 5.
    assert abs(model.expected_remaining(1) - 5.0) < 1e-9
    # At turn 3 only the 10-turn sessions survive: E[10-3] = 7.
    assert abs(model.expected_remaining(3) - 7.0) < 1e-9
    # Deeper than anything observed: conversation is wrapping up.
    assert model.expected_remaining(11) == 1.0


def test_continuation_changes_routing_economics():
    # Simple task behind a large cached prefix: switching only pays if the
    # conversation is expected to keep going.
    big_turn = {"role": "user", "content": [
        {"type": "text", "text": "x" * 400_000, "cache_control": {"type": "ephemeral"}}]}
    body = {"model": "claude-opus-4-8", "max_tokens": 512,
            "messages": [big_turn, {"role": "assistant", "content": "ok"},
                         {"role": "user", "content": "Summarize the key points of the above."}]}
    short = recommend(body, expected_remaining_turns=1)
    long = recommend(body, expected_remaining_turns=40)
    assert short.action == "stay"
    assert long.action == "switch"


def test_ledger_session_tracking(tmp_path):
    ledger = Ledger(str(tmp_path / "t.db"))
    rec = recommend(_body(CLASSIFY))
    usage = Usage(input_tokens=100, output_tokens=10)
    for turn in range(3):
        ledger.record(mode="shadow", recommendation=rec, routed_model=rec.original_model,
                      applied=False, status_code=200, usage=usage, session_key="sess-a")
    ledger.record(mode="shadow", recommendation=rec, routed_model=rec.original_model,
                  applied=False, status_code=200, usage=usage, session_key="sess-b")
    assert ledger.turns_so_far("sess-a") == 3
    assert ledger.turns_so_far("sess-b") == 1
    assert ledger.turns_so_far("") == 0
    assert sorted(ledger.session_lengths()) == [1, 3]
    ledger.close()


def _seeded_ledger(tmp_path):
    ledger = Ledger(str(tmp_path / "d.db"))
    usage_cheap = Usage(input_tokens=1_000, output_tokens=200)
    rec = recommend(_body(CLASSIFY))
    for i in range(40):
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                      applied=True, status_code=200, usage=usage_cheap, arm="treatment",
                      session_key=f"s{i}")
    for i in range(35):
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.original_model,
                      applied=False, status_code=200, usage=usage_cheap, arm="control",
                      session_key=f"c{i}")
    return ledger


def test_collect_stats_and_rct(tmp_path):
    ledger = _seeded_ledger(tmp_path)
    stats = collect_stats(ledger, days=0)
    assert stats["summary"]["n"] == 75
    assert stats["rct"]["ready"]
    assert stats["rct"]["saving_pct"] > 0.5  # haiku vs opus on identical tokens
    assert stats["daily"]
    assert stats["daily_mix"]
    ledger.close()


def test_dashboard_html_renders(tmp_path):
    ledger = _seeded_ledger(tmp_path)
    html = render_html(collect_stats(ledger, days=0))
    for marker in ("ModelPilot", "Cumulative savings", "Verified saving",
                   "model mix", "<svg", "classification"):
        assert marker in html, marker
    ledger.close()
