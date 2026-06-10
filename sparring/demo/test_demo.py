#!/usr/bin/env python3
"""Offline smoke test for the Phase 0 demo — no API key required.

Mocks the Anthropic client to verify everything around the model calls:
state-machine sequencing, transcript structure, early-quit handling, the
cacheable system-prompt layout, and the judge's citation-voiding rule.

Run:  python test_demo.py
"""

import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeStream:
    """Stands in for client.messages.stream(...) — also validates the request shape."""

    def __init__(self, kwargs):
        system = kwargs["system"]
        assert len(system) == 2, "system must be [base contract, state directive]"
        assert system[0].get("cache_control") == {"type": "ephemeral"}, \
            "base contract must carry the cache breakpoint"
        assert kwargs["thinking"] == {"type": "adaptive"}
        phase = system[1]["text"].splitlines()[0]
        self.text = f"(mock claude reply for: {phase})"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def text_stream(self):
        yield self.text

    def get_final_message(self):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)])


def fake_client():
    return SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw: FakeStream(kw)))


def test_full_session(orch, tmp):
    orch.TRANSCRIPT_DIR = tmp
    orch.anthropic = SimpleNamespace(Anthropic=fake_client)
    answers = [f"scripted candidate answer {i}" for i in range(1, 11)]

    json_path = orch.run_session(HERE / "scenarios" / "ship_or_slip.yaml", "smoke-test",
                                 candidate_fn=lambda msgs: answers.pop(0) if answers else None)
    transcript = json.loads(json_path.read_text())

    assert transcript["completed"] is True
    claude_turns = [t for t in transcript["turns"] if t["speaker"] == "claude"]
    cand_turns = [t for t in transcript["turns"] if t["speaker"] == "candidate"]
    assert len(claude_turns) == 11, f"expected 11 claude turns, got {len(claude_turns)}"
    assert len(cand_turns) == 10, f"expected 10 candidate turns, got {len(cand_turns)}"

    # States appear in machine order, and indices are sequential
    order = ["warmup", "position", "pressure_1", "pressure_2", "fact_injection", "rebuttal", "close"]
    seen = [t["state"] for t in transcript["turns"]]
    assert [s for i, s in enumerate(seen) if i == 0 or s != seen[i - 1]] == order
    assert [t["idx"] for t in transcript["turns"]] == list(range(1, 22))
    assert json_path.with_suffix(".md").exists()
    print("PASS full session: 21 turns, states in order, transcript + md written")
    return json_path


def test_early_quit(orch, tmp):
    orch.TRANSCRIPT_DIR = tmp
    orch.anthropic = SimpleNamespace(Anthropic=fake_client)
    answers = ["a1", "a2", "a3"]

    json_path = orch.run_session(HERE / "scenarios" / "sunset_beloved_product.yaml", "quitter",
                                 candidate_fn=lambda msgs: answers.pop(0) if answers else None)
    transcript = json.loads(json_path.read_text())

    assert transcript["completed"] is False
    assert transcript["turns"][-1]["state"] == "close", "close must still run after early quit"
    assert len([t for t in transcript["turns"] if t["speaker"] == "candidate"]) == 3
    print("PASS early quit: partial transcript saved, close state still delivered")


def test_judge_citation_voiding(judge, session_json: Path):
    transcript = json.loads(session_json.read_text())
    cand_idx = [t["idx"] for t in transcript["turns"] if t["speaker"] == "candidate"]
    claude_idx = [t["idx"] for t in transcript["turns"] if t["speaker"] == "claude"]

    report = judge.JudgeReport(
        scores=[
            judge.DimensionScore(dimension="position_quality", score=4,
                                 cited_turns=[cand_idx[0]], rationale="grounded"),
            judge.DimensionScore(dimension="updating", score=2,
                                 cited_turns=[claude_idx[0]], rationale="cites interviewer only"),
            judge.DimensionScore(dimension="synthesis", score=5,
                                 cited_turns=[99999], rationale="cites a turn that doesn't exist"),
        ],
        key_moments=[judge.KeyMoment(turn=cand_idx[0], label="test", comment="c")],
        summary="mock summary",
    )
    judge.anthropic = SimpleNamespace(Anthropic=lambda: SimpleNamespace(
        messages=SimpleNamespace(parse=lambda **kw: SimpleNamespace(parsed_output=report))))

    out_path = judge.judge(session_json)
    out = json.loads(out_path.read_text())
    kept = {s["dimension"] for s in out["report"]["scores"]}
    assert kept == {"position_quality"}, f"only the validly-cited score should survive, got {kept}"
    assert set(out["voided_dimensions"]) == {"updating", "synthesis"}
    print("PASS judge: scores citing interviewer/nonexistent turns voided, valid score kept")


def test_simulate_role_flip(simulate):
    captured = {}

    def fake_create(**kw):
        captured.update(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="sim answer")])

    simulate.anthropic = SimpleNamespace(Anthropic=lambda: SimpleNamespace(
        messages=SimpleNamespace(create=fake_create)))

    scenario = simulate.orch.load_scenario(HERE / "scenarios" / "ship_or_slip.yaml")
    fn = simulate.make_candidate_fn(scenario, "weak")
    messages = [
        {"role": "user", "content": "(The candidate has joined the session.)"},
        {"role": "assistant", "content": "interviewer greeting"},
        {"role": "user", "content": "candidate reply 1"},
        {"role": "assistant", "content": "interviewer challenge"},
    ]
    assert fn(messages) == "sim answer"
    flipped = captured["messages"]
    # Kickoff dropped; interviewer turns become user turns and vice versa
    assert [m["role"] for m in flipped] == ["user", "assistant", "user"]
    assert flipped[0]["content"] == "interviewer greeting"
    assert "Northwind" in captured["system"][0]["text"], "candidate must get the scenario brief"
    assert "mediocre" in captured["system"][0]["text"], "persona must be applied"
    print("PASS simulate: roles flipped, kickoff dropped, persona + brief in system prompt")


def main():
    orch = load("orchestrator")
    judge = load("judge")
    simulate = load("simulate")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        session_json = test_full_session(orch, tmp)
        test_early_quit(orch, tmp)
        test_judge_citation_voiding(judge, session_json)
        test_simulate_role_flip(simulate)
    print("\nAll offline smoke tests passed.")


if __name__ == "__main__":
    main()
