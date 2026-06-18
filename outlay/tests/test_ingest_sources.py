"""The live-source adapters: parsers (offline fixtures) + paginating clients
(canned transports). No network, no credentials."""

from pathlib import Path

from outlay.attribute import attribute
from outlay.ingest import (
    AnthropicAdminClient,
    CursorAdminClient,
    parse_admin_usage_report,
    parse_claude_code_transcript,
    parse_cursor_events,
    parse_github_issues,
)
from outlay.ingest._http import get_json, post_json
from outlay.join import IdentityGraph, JoinEngine
from outlay.models import FidelityTier

FIX = Path(__file__).parent.parent / "fixtures"


# ---- Claude Code: the branch-bearing, ticket-level source ----

def test_claude_code_carries_branch_and_session():
    events = parse_claude_code_transcript(FIX / "claude_code_session.jsonl", user="alice@acme.dev")
    # 3 assistant turns with usage; user turns + tool results skipped.
    assert len(events) == 3
    e = events[0]
    assert e.branch == "feature/108-usage-export"
    assert e.session_id == "cc-sess-108"
    assert e.cache_read_tokens == 300000


def test_claude_code_reaches_ticket_via_branch():
    events = parse_claude_code_transcript(FIX / "claude_code_session.jsonl", user="alice@acme.dev")
    work = parse_github_issues(FIX / "github_issues.json")
    res = attribute(events, work)
    # GH-108 and GH-107 were open with no spend in the per-call fixture; Claude
    # Code branch data attributes to them at BRANCH fidelity.
    assert "GH-108" in res.rollups and "GH-107" in res.rollups
    assert all(r.fidelity == FidelityTier.BRANCH for r in res.rows)


# ---- Anthropic Admin API: aggregated -> team/invoice fidelity ----

def test_admin_report_parse_and_cache_variants():
    events = parse_admin_usage_report({"data": [
        {"starting_at": "2026-06-07T00:00:00Z", "results": [
            {"api_key_id": "k", "model": "claude-sonnet-4-6",
             "uncached_input_tokens": 100, "output_tokens": 10,
             "cache_read_input_tokens": 50,
             "cache_creation": {"ephemeral_5m_input_tokens": 5, "ephemeral_1h_input_tokens": 2}},
        ]},
    ]})
    assert events[0].input_tokens == 100
    assert events[0].cache_write_tokens == 7  # 5m + 1h breakdown summed
    assert events[0].api_key_id == "k"


def test_admin_events_degrade_to_team_or_invoice():
    events = parse_admin_usage_report(__import__("json").loads(
        (FIX / "anthropic_admin_report.json").read_text()))
    work = parse_github_issues(FIX / "github_issues.json")
    ident = IdentityGraph(key_to_user={"key_ci": "ci-bot@acme.dev"},
                          user_to_team={"ci-bot@acme.dev": "platform"})
    res = attribute(events, work, engine=JoinEngine(work, identity=ident))
    fids = {r.fidelity for r in res.rows}
    # mapped key -> TEAM; unmapped key -> INVOICE. Never branch/call.
    assert fids <= {FidelityTier.TEAM, FidelityTier.INVOICE}
    assert FidelityTier.TEAM in fids and FidelityTier.INVOICE in fids
    assert res.ticket_coverage == 0.0  # aggregated source can't reach a ticket


def test_admin_client_paginates():
    pages = [
        {"data": [{"starting_at": "2026-06-07T00:00:00Z", "results": [
            {"api_key_id": "k", "model": "claude-sonnet-4-6", "uncached_input_tokens": 1}]}],
         "has_more": True, "next_page": "p2"},
        {"data": [{"starting_at": "2026-06-08T00:00:00Z", "results": [
            {"api_key_id": "k", "model": "claude-sonnet-4-6", "uncached_input_tokens": 2}]}],
         "has_more": False},
    ]
    calls = {"n": 0}

    def transport(method, url, headers, body):
        assert headers["x-api-key"] == "sk-ant-admin-test"
        i = calls["n"]; calls["n"] += 1
        return pages[i]

    client = AnthropicAdminClient(api_key="sk-ant-admin-test", transport=transport)
    events = client.pull("2026-06-07T00:00:00Z")
    assert calls["n"] == 2 and len(events) == 2


# ---- Cursor Admin API: per-user -> team fidelity ----

def test_cursor_parse():
    events = parse_cursor_events(__import__("json").loads(
        (FIX / "cursor_events.json").read_text()))
    assert len(events) == 3
    assert events[0].provider == "cursor"
    assert events[0].user == "alice@acme.dev"
    assert events[0].cache_read_tokens == 80000
    assert events[0].branch is None  # cursor exposes no branch


def test_cursor_client_basic_auth_and_merge():
    seen = {}

    def transport(method, url, headers, body):
        seen["auth"] = headers["authorization"]
        return {"usageEvents": [{"id": "a", "model": "claude-opus-4-8",
                                 "userEmail": "x@y.z", "tokenUsage": {"inputTokens": 5}}],
                "pagination": {"hasNextPage": False}}

    client = CursorAdminClient(api_key="cur_key", transport=transport)
    events = client.pull(0, 1)
    assert seen["auth"].startswith("Basic ")
    assert len(events) == 1


# ---- http seam sanity ----

def test_http_helpers_use_injected_transport():
    def t(method, url, headers, body):
        return {"method": method, "had_body": body is not None}

    assert get_json("http://x", {}, t)["method"] == "GET"
    assert post_json("http://x", {}, {"a": 1}, t)["had_body"] is True
