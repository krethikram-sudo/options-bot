"""Non-inferiority judging.

Two graders, used in this order of preference:
  1. Programmatic — when the prompt has an `expected` answer (classification,
     extraction), grade by normalized match. Beats any judge.
  2. LLM judge — pairwise candidate-vs-baseline with position swap: the
     candidate passes only if it is judged non-inferior in BOTH presentation
     orders. This kills the judge's position bias at the cost of 2 calls.

Known residual bias (a Claude judge grading Claude outputs) is audited by the
human calibration set — see ROUTER_TUNING_PLAN.md §3.
"""

import json
import re

JUDGE_MODEL = "claude-opus-4-8"

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "candidate_non_inferior": {"type": "boolean"},
        "defect": {"type": "string"},
    },
    "required": ["candidate_non_inferior", "defect"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM = (
    "You grade whether a CANDIDATE response is non-inferior to a BASELINE "
    "response for the same request. Non-inferior means: a careful reader with "
    "the task's goals would not be worse off receiving the candidate. Judge "
    "task success only — ignore style, verbosity, and formatting differences "
    "unless the task is about them. If the candidate contains an error, "
    "omission, or misunderstanding the baseline avoids, it is inferior; name "
    "the defect. If both are wrong in the same way, the candidate is "
    "non-inferior."
)


def _norm(text: str) -> str:
    return re.sub(r"[\s\.\,\!\:\;\"\']+", " ", text.strip().lower()).strip()


def programmatic_grade(expected: str, candidate_text: str) -> bool:
    """Exact-answer tasks: the expected answer must appear, normalized."""
    return _norm(expected) in _norm(candidate_text)


def _extract_verdict(text: str) -> bool:
    """Parse the JSON verdict, tolerating prose around it (when the SDK can't
    enforce a schema and the model wraps the JSON in text)."""
    try:
        return bool(json.loads(text)["candidate_non_inferior"])
    except (ValueError, KeyError, TypeError):
        m = re.search(r'\{.*"candidate_non_inferior".*\}', text, re.DOTALL)
        if m:
            return bool(json.loads(m.group(0))["candidate_non_inferior"])
        raise


def _ask(client, prompt: str, first: str, second: str, candidate_position: str) -> bool:
    content = (
        f"<request>\n{prompt}\n</request>\n\n"
        f"<response_one>\n{first}\n</response_one>\n\n"
        f"<response_two>\n{second}\n</response_two>\n\n"
        f"The CANDIDATE is response_{candidate_position}; the other is the BASELINE."
    )
    base = dict(model=JUDGE_MODEL, max_tokens=400, system=_JUDGE_SYSTEM,
                messages=[{"role": "user", "content": content}])
    try:
        response = client.messages.create(
            output_config={"format": {"type": "json_schema", "schema": _VERDICT_SCHEMA}},
            **base,
        )
    except TypeError:
        # Older SDK without output_config: ask for JSON in the prompt instead.
        base["messages"][0]["content"] += (
            '\n\nReply with ONLY this JSON, nothing else: '
            '{"candidate_non_inferior": true|false, "defect": "<text>"}')
        response = client.messages.create(**base)
    text = next(b.text for b in response.content if b.type == "text")
    return _extract_verdict(text)


def judge_pair(client, prompt: str, baseline_text: str, candidate_text: str) -> bool:
    """Position-debiased pairwise verdict: pass requires both orders to agree."""
    return (
        _ask(client, prompt, candidate_text, baseline_text, candidate_position="one")
        and _ask(client, prompt, baseline_text, candidate_text, candidate_position="two")
    )


def judge_prompt(client, prompt_row: dict, outputs_by_model: dict[str, str],
                 baseline_model: str) -> dict[str, bool]:
    """Judge every cheaper model's output against the baseline's.

    Returns {model: non_inferior} for every model with an output. The baseline
    is non-inferior to itself by definition; errored models are inferior.
    """
    baseline_text = outputs_by_model.get(baseline_model)
    verdicts: dict[str, bool] = {}
    for model, text in outputs_by_model.items():
        if model == baseline_model:
            verdicts[model] = True
        elif text is None:
            verdicts[model] = False
        elif "expected" in prompt_row:
            verdicts[model] = programmatic_grade(prompt_row["expected"], text)
        elif baseline_text is None:
            verdicts[model] = False  # nothing to compare against — fail safe
        else:
            verdicts[model] = judge_pair(client, prompt_row["prompt"], baseline_text, text)
    return verdicts
