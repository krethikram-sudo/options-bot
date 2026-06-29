"""Client-side work vs. non-work classifier — runs in the thin client / gateway, on
the **customer's own box**. It reads the prompt LOCALLY and emits only a one-word
label (`work` / `non_work` / `unknown`). The prompt never leaves the environment;
Outlay consumes the label, not the text.

This is the optional **Tier-2** signal behind the work/non-work feature: most spend
is classified from metadata (the attribution join + the work-key registry); this
adds prompt-level judgement for the unjoined remainder, **without exfiltrating
prompts**. Stdlib-only and lexical (regex heuristics) so it is safe to publish in
the thin client — it carries no economics or server-side IP.

Honesty matches the server engine: when the signal is weak or mixed we return
`unknown`, never *guess* `non_work`. The customer can tune `WorkRules`
(extra work/non-work phrases, their own repo/domain markers).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- default lexical signals (lowercased match on the last user message) -------
# Work: software + professional/company task language.
_WORK = re.compile(
    r"```|\b(def |class |function|import |select\b.+\bfrom\b|traceback|stack ?trace|"
    r"git |pull request|\bpr\b|merge|deploy|rollback|bug ?fix|refactor|unit test|"
    r"endpoint|api|schema|migration|kubernetes|terraform|docker|"
    r"ticket|jira|linear|sprint|epic|backlog|standup|"
    r"customer|invoice|contract|spec|requirement|roadmap|stakeholder|kpi|okrs?|"
    r"incident|postmortem|runbook|on-?call|sla|compliance|audit)\b",
    re.IGNORECASE)

# Non-work: personal / leisure / clearly-not-company-business.
_NON_WORK = re.compile(
    r"\b(recipe|cook|dinner|meal plan|grocery|"
    r"vacation|holiday trip|flight|hotel|airbnb|itinerary|things to do in|"
    r"movie|tv show|netflix|video game|gaming|playthrough|song lyrics|"
    r"workout|gym routine|diet|weight loss|calorie|"
    r"dating|tinder|relationship advice|horoscope|astrology|"
    r"birthday gift|christmas gift|shopping for|buy a |"
    r"homework|my essay|college application|personal statement|"
    r"fantasy football|sports score|joke|meme)\b",
    re.IGNORECASE)


@dataclass
class WorkRules:
    """Customer tuning. Extra phrases (matched literally, case-insensitive) and
    domain/repo markers that should always count as work."""

    work_terms: tuple = ()
    non_work_terms: tuple = ()
    work_markers: tuple = ()   # e.g. ("acme.com", "github.com/acme/") — company repos/domains


@dataclass
class WorkLabel:
    label: str          # "work" | "non_work" | "unknown"
    confidence: float   # 0..1, |work_hits - non_work_hits| based
    rationale: str


def _last_user_text(body: dict) -> str:
    """The final user message from an Anthropic /v1/messages-style body, as text."""
    msgs = (body or {}).get("messages") or []
    for m in reversed(msgs):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _count(pattern: re.Pattern, text: str) -> int:
    return len(pattern.findall(text or ""))


def classify_worktype(body: dict, rules: WorkRules | None = None) -> WorkLabel:
    """Label one request `work` / `non_work` / `unknown` from its prompt — locally.

    Precedence: a company work-marker (repo/domain) forces `work`; otherwise we
    score default + custom work vs. non-work signals. A clear majority decides;
    a tie or no signal is `unknown` (we don't guess non-work)."""
    rules = rules or WorkRules()
    text = _last_user_text(body)
    low = text.lower()

    # 1. Company marker → unambiguously work.
    for mk in rules.work_markers:
        if mk and mk.lower() in low:
            return WorkLabel("work", 1.0, f"matched work marker '{mk}'")

    work = _count(_WORK, text) + sum(1 for t in rules.work_terms if t and t.lower() in low)
    non = _count(_NON_WORK, text) + sum(1 for t in rules.non_work_terms if t and t.lower() in low)

    if work == 0 and non == 0:
        return WorkLabel("unknown", 0.0, "no work or non-work signal in the prompt")
    if work > non:
        return WorkLabel("work", min(1.0, (work - non) / max(work, 1)), f"{work} work vs {non} non-work signals")
    if non > work:
        return WorkLabel("non_work", min(1.0, (non - work) / max(non, 1)), f"{non} non-work vs {work} work signals")
    return WorkLabel("unknown", 0.0, f"tied ({work} work, {non} non-work) — not guessed")


def label_only(body: dict, rules: WorkRules | None = None) -> str:
    """The one value that may leave the box: the label string. The prompt does not."""
    return classify_worktype(body, rules).label
