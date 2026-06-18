"""Live planner pullers — pagination + auth, exercised with canned transports."""

from scopepilot.ingest import GitHubIssuesClient, JiraClient, LinearClient


def test_github_client_pagination_filters_prs_and_auths():
    pages = [
        [{"number": 1, "title": "a", "state": "open", "labels": []},
         {"number": 2, "title": "pr", "state": "open", "pull_request": {"url": "x"}}],  # PR -> dropped
        [{"number": 3, "title": "c", "state": "closed", "labels": [],
          "merged_at": "2026-06-01T00:00:00Z"}],
    ]
    seen = {"n": 0, "auth": None}

    def transport(method, url, headers, body):
        seen["auth"] = headers.get("authorization")
        i = seen["n"]; seen["n"] += 1
        return pages[i] if i < len(pages) else []

    client = GitHubIssuesClient(token="ghp_x", transport=transport)
    items = client.pull("acme", "repo", page_size=2)
    assert seen["auth"] == "Bearer ghp_x"
    assert [w.ticket_id for w in items] == ["GH-1", "GH-3"]   # PR #2 filtered out


def test_jira_client_classic_offset_pagination_and_auth():
    pages = [
        {"issues": [{"key": "OPS-1", "fields": {"summary": "a"}},
                    {"key": "OPS-2", "fields": {"summary": "b"}}],
         "startAt": 0, "maxResults": 2, "total": 3},
        {"issues": [{"key": "OPS-3", "fields": {"summary": "c"}}],
         "startAt": 2, "maxResults": 2, "total": 3},
    ]
    seen = {"n": 0, "auth": None}

    def transport(method, url, headers, body):
        seen["auth"] = headers["authorization"]
        i = seen["n"]; seen["n"] += 1
        return pages[i]

    client = JiraClient(base_url="https://acme.atlassian.net",
                        email="me@acme.dev", api_token="tok", transport=transport)
    items = client.pull("project = OPS")
    assert seen["n"] == 2 and seen["auth"].startswith("Basic ")
    assert [w.ticket_id for w in items] == ["OPS-1", "OPS-2", "OPS-3"]


def test_jira_client_token_pagination():
    pages = [
        {"issues": [{"key": "OPS-1", "fields": {}}], "nextPageToken": "t2", "isLast": False},
        {"issues": [{"key": "OPS-2", "fields": {}}], "isLast": True},
    ]
    n = {"i": 0}

    def transport(method, url, headers, body):
        r = pages[n["i"]]; n["i"] += 1
        return r

    items = JiraClient(transport=transport).pull("project = OPS")
    assert [w.ticket_id for w in items] == ["OPS-1", "OPS-2"]


def test_linear_client_cursor_pagination_and_auth():
    pages = [
        {"data": {"issues": {
            "nodes": [{"identifier": "ENG-1", "state": {"type": "completed"}}],
            "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}}},
        {"data": {"issues": {
            "nodes": [{"identifier": "ENG-2", "state": {"type": "started"}}],
            "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
    ]
    seen = {"n": 0, "auth": None, "had_query": False}

    def transport(method, url, headers, body):
        import json
        seen["auth"] = headers["authorization"]
        seen["had_query"] = b"issues" in body
        i = seen["n"]; seen["n"] += 1
        return pages[i]

    client = LinearClient(api_key="lin_key", transport=transport)
    items = client.pull(filter={"team": {"key": {"eq": "ENG"}}})
    assert seen["n"] == 2 and seen["auth"] == "lin_key" and seen["had_query"]
    assert [w.ticket_id for w in items] == ["ENG-1", "ENG-2"]
    assert items[0].status == "done" and items[1].status == "in_progress"
