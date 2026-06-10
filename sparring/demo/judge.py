#!/usr/bin/env python3
"""Sparring Phase 0 demo — judge pass: score a debate transcript against the rubric.

Runs in a separate context from the debate agent. Every score must cite specific
candidate turns; a score without citations is voided (no citation, no score).
Output is decision support for a human reviewer, never a verdict.

Usage:
    python judge.py transcripts/<session>.json
"""

import argparse
import json
import sys
from pathlib import Path

import anthropic
import yaml
from pydantic import BaseModel, Field

MODEL = "claude-opus-4-8"
RUBRIC_PATH = Path(__file__).parent / "rubric.yaml"

JUDGE_SYSTEM = """\
You are the scoring judge for a structured debate-based interview assessment. You will read
a transcript of a candidate debating an AI interviewer on a product-management case, and
score the CANDIDATE (never the interviewer) against the rubric provided.

Rules:
- Score only what is in the transcript. Do not reward eloquence over substance.
- Every dimension score MUST cite the specific turn numbers (the [n] indices of CANDIDATE
  turns) that justify it. A score you cannot ground in cited turns must not be given.
- Calibrate to the anchors. A 3 is a competent performance; 5s are rare and earned.
- Identify 3-6 key moments: the turns a hiring reviewer should read first (best argument,
  a dodge, a concession handled well or poorly, the response to new information).
- Your summary is decision support for a human reviewer. Describe what the transcript shows
  about how this person reasons. Do NOT give a hire/no-hire recommendation.
- If the session ended early or a phase is missing, score only the dimensions the
  transcript supports and say so in the summary."""


class DimensionScore(BaseModel):
    dimension: str = Field(description="Rubric dimension name, exactly as given")
    score: int = Field(ge=1, le=5)
    cited_turns: list[int] = Field(description="Candidate turn indices grounding this score")
    rationale: str = Field(description="2-3 sentences tying the cited turns to the anchors")


class KeyMoment(BaseModel):
    turn: int
    label: str = Field(description="Short tag, e.g. 'strongest argument', 'dodge', 'good concession'")
    comment: str


class JudgeReport(BaseModel):
    scores: list[DimensionScore]
    key_moments: list[KeyMoment]
    summary: str = Field(description="4-8 sentences on how this candidate reasons; no hire/no-hire verdict")


def format_rubric(rubric: dict) -> str:
    parts = []
    for dim in rubric["dimensions"]:
        anchors = "\n".join(f"    {k}: {v}" for k, v in dim["anchors"].items())
        parts.append(f"- {dim['name']}: {dim['description'].strip()}\n  Anchors:\n{anchors}")
    return "\n".join(parts)


def format_transcript(transcript: dict) -> str:
    lines = []
    for turn in transcript["turns"]:
        speaker = "INTERVIEWER" if turn["speaker"] == "claude" else "CANDIDATE"
        lines.append(f"[{turn['idx']}] ({turn['state']}) {speaker}: {turn['text']}")
    return "\n\n".join(lines)


def judge(transcript_path: Path) -> Path:
    with open(transcript_path) as f:
        transcript = json.load(f)
    with open(RUBRIC_PATH) as f:
        rubric = yaml.safe_load(f)

    candidate_turns = {t["idx"] for t in transcript["turns"] if t["speaker"] == "candidate"}
    if not candidate_turns:
        sys.exit("Transcript contains no candidate turns; nothing to score.")

    prompt = (
        f"RUBRIC\n{format_rubric(rubric)}\n\n"
        f"SCENARIO: {transcript['scenario_title']}\n"
        f"SESSION COMPLETED: {transcript['completed']}\n\n"
        f"TRANSCRIPT\n{format_transcript(transcript)}\n\n"
        "Score the candidate on every rubric dimension the transcript supports."
    )

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_format=JudgeReport,
    )
    report: JudgeReport = response.parsed_output

    # No citation, no score — and citations must point at real candidate turns.
    voided = []
    valid_scores = []
    for s in report.scores:
        s.cited_turns = [t for t in s.cited_turns if t in candidate_turns]
        if s.cited_turns:
            valid_scores.append(s)
        else:
            voided.append(s.dimension)
    report.scores = valid_scores

    out = {
        "session_id": transcript["session_id"],
        "scenario_id": transcript["scenario_id"],
        "candidate": transcript.get("candidate", "anonymous"),
        "judge_model": MODEL,
        "voided_dimensions": voided,
        "report": report.model_dump(),
    }
    out_path = transcript_path.with_name(transcript_path.stem + "_judge.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print_report(out)
    print(f"\nJudge report saved: {out_path}")
    return out_path


def print_report(out: dict):
    report = out["report"]
    print(f"\n=== Judge report — {out['session_id']} ===\n")
    print("Scores (1-5):")
    for s in report["scores"]:
        cites = ", ".join(str(t) for t in s["cited_turns"])
        print(f"  {s['dimension']:<22} {s['score']}  (turns {cites})")
        print(f"    {s['rationale']}")
    if out["voided_dimensions"]:
        print(f"\n  Voided (no valid citations): {', '.join(out['voided_dimensions'])}")
    print("\nKey moments for the reviewer:")
    for m in report["key_moments"]:
        print(f"  [{m['turn']}] {m['label']}: {m['comment']}")
    print(f"\nSummary:\n{report['summary']}")
    print("\nNote: this report is decision support. A human reviews the transcript; no")
    print("automated hiring decision is made or implied.")


def main():
    parser = argparse.ArgumentParser(description="Score a Sparring transcript.")
    parser.add_argument("transcript", type=Path, help="Path to a transcript JSON file")
    args = parser.parse_args()
    judge(args.transcript)


if __name__ == "__main__":
    main()
