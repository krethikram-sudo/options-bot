"""Work vs non-work classification + the opt-in stop-non-work policy."""

from datetime import datetime

from outlay.models import UsageEvent
from outlay.worktype import (
    WorkPolicy,
    WorkType,
    classify_event,
    classify_usage,
    gateway_decision,
)


def _ev(id, **kw):
    return UsageEvent(id=id, provider="anthropic", model="claude-sonnet-4-6",
                      ts=datetime(2026, 1, 1), input_tokens=kw.pop("inp", 1_000_000),
                      output_tokens=kw.pop("out", 0), **kw)


# --------------------------- classification -------------------------------- #
def test_joined_to_work_is_work_from_metadata_only():
    # No prompt, no label — the attribution join alone marks it work.
    assert classify_event(_ev("1"), joined_to_work=True) is WorkType.WORK
    assert classify_event(_ev("2", explicit_ticket="GH-12")) is WorkType.WORK
    assert classify_event(_ev("3", branch="feature/123")) is WorkType.WORK


def test_work_key_registry_marks_work():
    pol = WorkPolicy(work_api_keys=frozenset({"key_ci"}))
    assert classify_event(_ev("1", api_key_id="key_ci"), policy=pol) is WorkType.WORK


def test_client_side_label_used_when_present():
    # The prompt never left the box — only the label reaches us.
    assert classify_event(_ev("1"), work_label="work") is WorkType.WORK
    assert classify_event(_ev("2"), work_label="non_work") is WorkType.NON_WORK


def test_non_work_key_overrides_everything():
    pol = WorkPolicy(non_work_api_keys=frozenset({"key_personal"}))
    # Even with a work label, an explicitly personal key is non-work.
    assert classify_event(_ev("1", api_key_id="key_personal"), work_label="work", policy=pol) is WorkType.NON_WORK


def test_unjoined_unlabeled_is_unknown_not_nonwork():
    # Fidelity-honest: don't call untracked spend non-work without evidence.
    assert classify_event(_ev("1")) is WorkType.UNKNOWN


def test_strict_mode_treats_unknown_as_nonwork():
    pol = WorkPolicy(treat_unknown_as_non_work=True)
    assert classify_event(_ev("1"), policy=pol) is WorkType.NON_WORK


# --------------------------- aggregation ----------------------------------- #
def test_classify_usage_split_and_rollups():
    events = [
        _ev("1", explicit_ticket="GH-1", user="a@co", api_key_id="k1"),      # work
        _ev("2", user="a@co", api_key_id="k1"),                              # unknown
        _ev("3", user="b@co", api_key_id="kp"),                              # non-work (label)
    ]
    pol = WorkPolicy()
    split = classify_usage(events, joined_ids={"1"}, labels={"3": "non_work"}, policy=pol)
    assert split.work_events == 1 and split.non_work_events == 1 and split.unknown_events == 1
    assert split.work_usd > 0 and split.non_work_usd > 0 and split.unknown_usd > 0
    # per-user rollup
    assert split.by_user["a@co"]["work_usd"] > 0 and split.by_user["a@co"]["unknown_usd"] > 0
    assert split.by_user["b@co"]["non_work_usd"] > 0
    assert 0.0 <= split.non_work_share <= 1.0


def test_non_work_share():
    events = [_ev("1", explicit_ticket="GH-1"), _ev("2")]  # work + unknown, no non-work
    split = classify_usage(events, joined_ids={"1"})
    assert split.non_work_share == 0.0


# --------------------------- enforcement (opt-in) -------------------------- #
def test_gateway_allows_by_default_even_for_non_work():
    # Read-only by default — nothing is blocked unless the customer opts in.
    d = gateway_decision(_ev("1"), work_label="non_work", policy=WorkPolicy())
    assert d.allow is True and d.work_type is WorkType.NON_WORK


def test_gateway_blocks_non_work_when_opted_in():
    pol = WorkPolicy(block_non_work=True)
    d = gateway_decision(_ev("1"), work_label="non_work", policy=pol)
    assert d.allow is False and "non-work" in d.reason


def test_gateway_block_unknown_strict():
    pol = WorkPolicy(block_non_work=True, block_unknown=True)
    assert gateway_decision(_ev("1"), policy=pol).allow is False          # unknown blocked
    assert gateway_decision(_ev("2"), joined_to_work=True, policy=pol).allow is True  # work allowed


def test_gateway_never_blocks_work():
    pol = WorkPolicy(block_non_work=True, block_unknown=True)
    d = gateway_decision(_ev("1", explicit_ticket="GH-9"), policy=pol)
    assert d.allow is True and d.work_type is WorkType.WORK
