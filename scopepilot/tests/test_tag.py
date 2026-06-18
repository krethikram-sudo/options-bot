"""Explicit task-tagging: source priority, detached-HEAD recovery, headers."""

import os

from scopepilot.tag import (
    TICKET_ENV,
    resolve_ticket,
    tagged,
    work_headers,
)


def test_explicit_arg_wins():
    ctx = resolve_ticket("PROJ-1", branch="feat/PROJ-2-x",
                         env={TICKET_ENV: "PROJ-3"})
    assert ctx.ticket_id == "PROJ-1" and ctx.source == "explicit_arg"


def test_env_beats_branch():
    ctx = resolve_ticket(branch="feat/PROJ-2-x", env={TICKET_ENV: "PROJ-9"})
    assert ctx.ticket_id == "PROJ-9" and ctx.source == "explicit_env"


def test_branch_resolution():
    ctx = resolve_ticket(branch="fix/PROJ-7-crash", commit_message="", env={})
    assert ctx.ticket_id == "PROJ-7" and ctx.source == "branch"


def test_detached_head_recovered_from_ci_env():
    # The killer case: branch is HEAD (detached), but CI exposes the PR branch.
    ctx = resolve_ticket(branch="HEAD", commit_message="",
                         env={"GITHUB_HEAD_REF": "feature/PROJ-42-add-thing"})
    assert ctx.ticket_id == "PROJ-42" and ctx.source == "ci"


def test_commit_trailer_fallback():
    ctx = resolve_ticket(branch="HEAD",
                         commit_message="Implement export\n\nTicket: PROJ-13",
                         env={})
    assert ctx.ticket_id == "PROJ-13" and ctx.source == "commit_trailer"


def test_commit_trailer_github_numeric():
    ctx = resolve_ticket(branch="HEAD", commit_message="Fix bug\n\nCloses #88", env={})
    assert ctx.ticket_id == "GH-88" and ctx.source == "commit_trailer"


def test_no_signal_returns_none():
    ctx = resolve_ticket(branch="HEAD", commit_message="just a tidy", env={})
    assert ctx.ticket_id is None and ctx.source == "none"


def test_work_headers_shape():
    h = work_headers("PROJ-5", "fix/PROJ-5-x")
    assert h == {"x-modelpilot-work-ticket": "PROJ-5",
                 "x-modelpilot-work-branch": "fix/PROJ-5-x"}
    assert work_headers() == {}


def test_tagged_context_sets_and_restores():
    env = {}
    with tagged("PROJ-77", env=env):
        assert env[TICKET_ENV] == "PROJ-77"
        assert resolve_ticket(branch="HEAD", commit_message="", env=env).ticket_id == "PROJ-77"
    assert TICKET_ENV not in env   # restored
