"""Ingestion adapters: external usage/planning data → Outlay records.

Each adapter is a pure parse from a provider/planner's native shape into
`UsageEvent` / `WorkItem`. Adapters are the unglamorous moat — the value is in
how many (provider × planner) shapes we can faithfully normalize, and at what
**fidelity** each can reach:

    Source                     Carries git branch?   Fidelity ceiling
    -------------------------  -------------------   ----------------
    Claude Code transcripts    yes  (gitBranch)      branch  (ticket-level)
    Outlay proxy metadata  yes  (tagged)         call    (ticket-level)
    Anthropic Admin API        no   (aggregated)     team    (key→user→team)
    Cursor Admin API           no   (per-user)       team    (user→team)

The branch-bearing sources do the ticket join; the aggregated ones reconcile
totals to the invoice. P0 ships all four parsers plus live pullers for the two
admin APIs.
"""

from .anthropic_admin import (
    AnthropicAdminClient,
    parse_admin_usage_report,
)
from .anthropic_usage import parse_anthropic_usage
from .bedrock import (
    parse_bedrock_invocation_logs,
    parse_bedrock_log_file,
    parse_bedrock_log_text,
)
from .claude_code import parse_claude_code_dir, parse_claude_code_transcript
from .cursor import CursorAdminClient, parse_cursor_events
from .github_issues import GitHubIssuesClient, parse_github_issues
from .jira import JiraClient, parse_jira_issues
from .linear import LinearClient, parse_linear_issues

# planner name → (WorkItem parser, ticket-resolver source for branch parsing)
PLANNERS = {
    "github": (parse_github_issues, "github"),
    "jira": (parse_jira_issues, "jira"),
    "linear": (parse_linear_issues, "linear"),
}

__all__ = [
    "parse_anthropic_usage",
    "parse_github_issues",
    "parse_jira_issues",
    "parse_linear_issues",
    "GitHubIssuesClient",
    "JiraClient",
    "LinearClient",
    "PLANNERS",
    "parse_admin_usage_report",
    "AnthropicAdminClient",
    "parse_claude_code_transcript",
    "parse_claude_code_dir",
    "parse_cursor_events",
    "CursorAdminClient",
    "parse_bedrock_invocation_logs",
    "parse_bedrock_log_text",
    "parse_bedrock_log_file",
]
