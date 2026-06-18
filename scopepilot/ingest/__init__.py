"""Ingestion adapters: external usage/planning data → ScopePilot records.

Each adapter is a pure parse from a provider/planner's native JSON shape into
`UsageEvent` / `WorkItem`. Adapters are the unglamorous moat — the value is in
how many (provider × planner) shapes we can faithfully normalize. P0 ships the
Anthropic-usage and GitHub-Issues pair.
"""

from .anthropic_usage import parse_anthropic_usage
from .github_issues import parse_github_issues

__all__ = ["parse_anthropic_usage", "parse_github_issues"]
