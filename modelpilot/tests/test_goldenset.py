import json
from types import SimpleNamespace

from modelpilot.goldenset.evaluate import evaluate
from modelpilot.goldenset.fanout import build_requests
from modelpilot.goldenset.judge import judge_pair, judge_prompt, programmatic_grade
from modelpilot.goldenset.label import label_from_verdicts


class FakeJudgeClient:
    """Returns a verdict computed by `verdict_fn(first_text)` so tests can
    simulate position bias."""

    def __init__(self, verdict_fn):
        self._fn = verdict_fn
        self.messages = SimpleNamespace(create=self._create)
        self.calls = []

    def _create(self, **kwargs):
        user_text = kwargs["messages"][0]["content"]
        first = user_text.split("<response_one>\n")[1].split("\n</response_one>")[0]
        self.calls.append(first)
        payload = json.dumps({"candidate_non_inferior": self._fn(first), "defect": ""})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=payload)])


def test_build_requests_covers_all_pairs():
    prompts = [{"id": "p1", "prompt": "hello"}, {"id": "p2", "prompt": "world"}]
    reqs = build_requests(prompts, models=["m-a", "m-b"])
    assert len(reqs) == 4
    assert {r["custom_id"] for r in reqs} == {"p1::m-a", "p1::m-b", "p2::m-a", "p2::m-b"}
    assert all(r["params"]["messages"][0]["content"] in ("hello", "world") for r in reqs)


def test_programmatic_grade_normalizes():
    assert programmatic_grade("Positive", "The sentiment is: POSITIVE.")
    assert not programmatic_grade("positive", "This is negative.")


def test_judge_pair_requires_both_orders():
    # Judge that always says non-inferior -> pass.
    assert judge_pair(FakeJudgeClient(lambda first: True), "q", "base", "cand")
    # Judge with position bias (only approves when candidate is shown first) -> fail.
    assert not judge_pair(FakeJudgeClient(lambda first: first == "cand"), "q", "base", "cand")


def test_judge_prompt_prefers_programmatic_grading():
    client = FakeJudgeClient(lambda first: False)  # would fail everything
    verdicts = judge_prompt(
        client,
        {"id": "p1", "prompt": "classify", "expected": "positive"},
        {"claude-haiku-4-5": "positive", "claude-opus-4-8": "positive"},
        baseline_model="claude-opus-4-8",
    )
    assert verdicts["claude-haiku-4-5"] is True
    assert client.calls == []  # no judge calls made


def test_label_is_cheapest_non_inferior():
    verdicts = {"claude-haiku-4-5": False, "claude-sonnet-4-6": True, "claude-opus-4-8": True}
    assert label_from_verdicts(verdicts, "claude-opus-4-8") == "claude-sonnet-4-6"
    verdicts["claude-haiku-4-5"] = True
    assert label_from_verdicts(verdicts, "claude-opus-4-8") == "claude-haiku-4-5"


def test_evaluate_threshold_sweep():
    labels = [
        # Router confidently says haiku for these; label agrees.
        {"id": "1", "prompt": "Classify this as positive or negative: 'great'", "label_model": "claude-haiku-4-5"},
        {"id": "2", "prompt": "Extract all emails from this text as JSON.", "label_model": "claude-haiku-4-5"},
        # Hard task; router stays on opus; label agrees.
        {"id": "3", "prompt": "Refactor the auth module across multiple files.", "label_model": "claude-opus-4-8"},
        # Label says haiku but the router will stay conservative -> missed, not false-downgrade.
        {"id": "4", "prompt": "Walk me through my options here.", "label_model": "claude-haiku-4-5"},
    ]
    report = evaluate(labels, baseline="claude-opus-4-8")
    assert report["n"] == 4
    # At a 0.99 gate nothing is applied: no false downgrades possible.
    strict = [r for r in report["by_threshold"] if r["threshold"] >= 0.9][-1]
    assert strict["false_downgrade"] == 0.0
    # The recommended gate meets the safety target.
    assert report["recommended"] is not None
    assert report["recommended"]["false_downgrade"] <= 0.02
    # And at that gate the easy wins are captured.
    assert report["recommended"]["coverage"] >= 0.5
