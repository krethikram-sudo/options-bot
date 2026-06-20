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


def test_bedrock_invocation_logs():
    """Bedrock model-invocation-log export -> UsageEvents (team-fidelity)."""
    from outlay.ingest import parse_bedrock_log_file
    from outlay.ingest.bedrock import normalize_model, actor_from_identity
    from outlay.pricing import cost_usd

    events = parse_bedrock_log_file(FIX / "bedrock_invocation_logs.jsonl")
    # 4 records, but one is a zero-token control line -> dropped
    assert len(events) == 3
    e = events[0]
    assert e.provider == "bedrock"
    assert e.model == "claude-sonnet-4-6"            # region + version stripped, mapped
    assert e.input_tokens == 1800 and e.output_tokens == 420
    assert e.cache_read_tokens == 1200               # cache split preserved
    assert e.user == "PaymentsSvcRole"               # actor from assumed-role ARN
    # the `usage`-block variant + cache write is parsed too
    opus = [x for x in events if x.model == "claude-opus-4-8"][0]
    assert opus.input_tokens == 3000 and opus.cache_write_tokens == 500
    assert opus.user == "PlatformRole"
    # iam user ARN resolves to the user name
    assert any(x.user == "alice" and x.model == "claude-haiku-4-5" for x in events)
    # every event prices without error (cache-aware)
    assert all(cost_usd(x) >= 0 for x in events)
    # model-id + identity helpers
    assert normalize_model("eu.anthropic.claude-haiku-4-5-v1:0") == "claude-haiku-4-5"
    assert actor_from_identity({"arn": "arn:aws:iam::1:user/bob"}) == "bob"


def test_bedrock_user_map_and_team_fidelity():
    """A user_map lets the identity graph reach team fidelity on Bedrock spend."""
    from outlay.ingest import parse_bedrock_log_file

    events = parse_bedrock_log_file(
        FIX / "bedrock_invocation_logs.jsonl",
        user_map={"PaymentsSvcRole": "payments@acme.dev", "PlatformRole": "platform@acme.dev"})
    ident = IdentityGraph(user_to_team={"payments@acme.dev": "growth",
                                        "platform@acme.dev": "platform"})
    res = attribute(events, [], engine=JoinEngine([], identity=ident))
    teams = {r.team_id for r in res.rows if r.team_id}
    assert "growth" in teams and "platform" in teams
    fids = {r.fidelity for r in res.rows}
    assert fids <= {FidelityTier.TEAM, FidelityTier.INVOICE}  # no branch -> never ticket-level


def test_cost_report_parse_and_paginate():
    """The org Cost Report (Anthropic's billed USD) parses + paginates -> reconciliation source."""
    from outlay.ingest import parse_cost_report
    from outlay.ingest.anthropic_admin import AnthropicAdminClient

    rep = {"data": [{"results": [{"amount": "6.40", "currency": "USD"}]},
                    {"results": [{"amount": "6.60"}]}]}
    assert parse_cost_report(rep) == 13.0

    pages = [
        {"data": [{"results": [{"amount": "2.00"}]}], "has_more": True, "next_page": "p2"},
        {"data": [{"results": [{"amount": "3.50"}]}], "has_more": False},
    ]
    calls = {"n": 0}

    def transport(method, url, headers, body):
        assert "cost_report" in url
        i = calls["n"]; calls["n"] += 1
        return pages[i]

    client = AnthropicAdminClient(api_key="sk-ant-admin-test", transport=transport)
    assert client.pull_cost("2026-06-01T00:00:00Z") == 5.5
    assert calls["n"] == 2
