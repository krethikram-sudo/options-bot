"""Tests for the client-side work/non-work prompt classifier (modelpilot/work_classify.py).

The classifier runs on the customer's box and emits ONLY a label — these tests
pin the label decisions (work / non_work / unknown), the honesty rule (weak or
mixed signal → unknown, never guessed non_work), company markers, and customer
tuning via WorkRules. They also assert that `label_only` exposes nothing but the
label string."""

from modelpilot.work_classify import (
    WorkLabel,
    WorkRules,
    classify_worktype,
    label_only,
    _last_user_text,
)


def _body(text):
    return {"messages": [{"role": "user", "content": text}]}


# --- work prompts -------------------------------------------------------------

def test_code_prompt_is_work():
    out = classify_worktype(_body("Refactor this function and fix the failing unit test"))
    assert out.label == "work"
    assert out.confidence > 0


def test_code_fence_is_work():
    out = classify_worktype(_body("why does this break?\n```\ndef f(): return 1/0\n```"))
    assert out.label == "work"


def test_professional_task_is_work():
    out = classify_worktype(_body("Draft the customer invoice and update the roadmap for this sprint"))
    assert out.label == "work"


# --- non-work prompts ---------------------------------------------------------

def test_recipe_prompt_is_non_work():
    out = classify_worktype(_body("Give me a recipe for dinner — something to cook with leftover grocery veg"))
    assert out.label == "non_work"
    assert out.confidence > 0


def test_vacation_prompt_is_non_work():
    out = classify_worktype(_body("Plan a vacation itinerary: flight, hotel, and things to do in Lisbon"))
    assert out.label == "non_work"


def test_leisure_prompt_is_non_work():
    out = classify_worktype(_body("Recommend a movie on netflix and a good video game to play tonight"))
    assert out.label == "non_work"


# --- unknown (honesty: never guess) ------------------------------------------

def test_empty_prompt_is_unknown():
    out = classify_worktype(_body("hello there"))
    assert out.label == "unknown"
    assert out.confidence == 0.0


def test_no_messages_is_unknown():
    assert classify_worktype({}).label == "unknown"
    assert classify_worktype({"messages": []}).label == "unknown"


def test_tie_is_unknown_not_guessed():
    # one work signal (deploy) and one non-work signal (recipe) → tie → unknown
    out = classify_worktype(_body("deploy notes, then a recipe for after"))
    assert out.label == "unknown"
    assert "tied" in out.rationale


# --- company markers ----------------------------------------------------------

def test_company_marker_forces_work():
    rules = WorkRules(work_markers=("github.com/acme/",))
    # leisure language, but it references the company repo → work
    out = classify_worktype(
        _body("can you watch this netflix movie context in github.com/acme/web"), rules
    )
    assert out.label == "work"
    assert out.confidence == 1.0
    assert "acme" in out.rationale


def test_company_domain_marker():
    rules = WorkRules(work_markers=("acme.com",))
    out = classify_worktype(_body("reply to this email from jo@acme.com"), rules)
    assert out.label == "work"


# --- customer tuning ----------------------------------------------------------

def test_custom_work_term():
    rules = WorkRules(work_terms=("widget pipeline",))
    base = classify_worktype(_body("look at the widget pipeline status"))
    tuned = classify_worktype(_body("look at the widget pipeline status"), rules)
    assert base.label == "unknown"
    assert tuned.label == "work"


def test_custom_non_work_term():
    rules = WorkRules(non_work_terms=("pickleball league",))
    tuned = classify_worktype(_body("organize the pickleball league bracket"), rules)
    assert tuned.label == "non_work"


# --- content-block (list) messages -------------------------------------------

def test_content_blocks_are_read():
    body = {
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "fix the "},
                {"type": "text", "text": "api endpoint migration"},
            ]},
        ]
    }
    assert classify_worktype(body).label == "work"


def test_last_user_message_wins():
    body = {"messages": [
        {"role": "user", "content": "recipe for dinner"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "now refactor the deploy script and fix the bug"},
    ]}
    assert _last_user_text(body) == "now refactor the deploy script and fix the bug"
    assert classify_worktype(body).label == "work"


# --- label_only is the only thing that leaves the box ------------------------

def test_label_only_returns_just_the_string():
    out = label_only(_body("Refactor this function"))
    assert out == "work"
    assert isinstance(out, str)


def test_label_only_handles_unknown():
    assert label_only(_body("hi")) == "unknown"


def test_worklabel_shape():
    out = classify_worktype(_body("Refactor this function"))
    assert isinstance(out, WorkLabel)
    assert out.label in {"work", "non_work", "unknown"}
    assert 0.0 <= out.confidence <= 1.0
    assert isinstance(out.rationale, str)
