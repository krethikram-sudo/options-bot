#!/usr/bin/env python3
"""Sparring Phase 0 demo — automated session: Claude plays the candidate too.

A second, separate Claude context answers as the candidate under a persona.
Running both personas on the same scenario and judging the transcripts is a
one-command miniature of the validity experiment (DISCOVERY_PLAN.md,
Experiment A): the judge's scores should clearly separate strong from weak.

Usage:
    python simulate.py scenarios/ship_or_slip.yaml --persona strong --judge
    python simulate.py scenarios/ship_or_slip.yaml --persona weak --judge
"""

import argparse
from pathlib import Path

import anthropic

import orchestrator as orch

CANDIDATE_MAX_TOKENS = 1200

PERSONAS = {
    "strong": """\
You are role-playing a genuinely strong Staff PM candidate in a debate-based interview.
Play the role consistently and never mention that you are simulating or role-playing.

How you operate:
- Commit to a clear position early and say plainly what it costs.
- Argue from the scenario's specific numbers and constraints, not generic frameworks.
- When the interviewer lands a real point, concede it explicitly and explain how it
  adjusts (or doesn't adjust) your position.
- When new information arrives, interrogate it first — reliability, causality, what would
  confirm it — then update the *shape* of your recommendation proportionately.
- Flag your own uncertainty honestly; never bluff a fact the scenario doesn't give you.
- Keep each answer to 4-8 sentences of substance.""",
    "weak": """\
You are role-playing a polished but mediocre PM candidate in a debate-based interview —
the eloquent-but-shallow profile that often fools panel interviews. Play the role
consistently and never mention that you are simulating or role-playing, and never break
character to be insightful.

How you operate:
- Sound confident and articulate, but avoid ever committing to a clear position; prefer
  "it depends", "both options have merit", and balanced-sounding hedges.
- Lean on framework name-drops (RICE, north-star metrics, "first principles", 80/20)
  instead of the scenario's actual numbers.
- When challenged, either restate your earlier points in new words or smoothly change
  the subject; do not engage the strongest version of the objection.
- When new information arrives, either wave it off or instantly flip your stance without
  analysis — whichever lets you avoid hard reasoning.
- Never explicitly concede a point, and never flag uncertainty.
- Keep each answer to 4-8 sentences. Stay plausible — not cartoonishly bad.""",
}

CANDIDATE_CONTEXT = """\

THE SCENARIO YOU WERE GIVEN
{brief}

You are speaking with the interviewer now. Respond only with what the candidate says —
no stage directions, no quotation marks, no meta-commentary."""


def make_candidate_fn(scenario: dict, persona: str):
    client = anthropic.Anthropic()
    system = PERSONAS[persona] + CANDIDATE_CONTEXT.format(brief=scenario["brief"].strip())

    def candidate_fn(messages: list) -> str:
        # Flip perspective: the interviewer's (assistant) turns become user turns for
        # the candidate model. Skip the orchestrator's kickoff line so the flipped
        # conversation starts with a user-role message as the API requires.
        flipped = [
            {"role": "user" if m["role"] == "assistant" else "assistant", "content": m["content"]}
            for m in messages[1:]
        ]
        response = client.messages.create(
            model=orch.MODEL,
            max_tokens=CANDIDATE_MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=flipped,
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        print(f"\nCandidate ({persona}): {text}")
        return text

    return candidate_fn


def main():
    parser = argparse.ArgumentParser(description="Run an automated Sparring session.")
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    parser.add_argument("--judge", action="store_true", help="Run the judge pass afterwards")
    args = parser.parse_args()

    scenario = orch.load_scenario(args.scenario)
    candidate_fn = make_candidate_fn(scenario, args.persona)
    json_path = orch.run_session(args.scenario, f"sim-{args.persona}", candidate_fn)

    if args.judge:
        import judge
        judge.judge(json_path)


if __name__ == "__main__":
    main()
