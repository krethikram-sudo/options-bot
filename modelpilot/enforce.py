"""Program hard-cap enforcement for the in-path gateway.

Pulls the current enforcement verdict from the console — which *programs* are over
their hard cap, and the action (block / route-down) — and matches each request's
declared work context to it **locally**, so there's no per-call round trip.

Fail-open by design: if the console is unreachable we keep the last good verdict;
if we've never fetched one, nothing is enforced. We never block a customer's
traffic because *our* control plane had a blip — only because a budget the
customer set was actually exceeded.

Read-only contract: the console returns the verdict; the gateway acts on it here.
Contains no routing/pricing IP — safe to ship in the published thin client.
"""

from __future__ import annotations

import os


def _project_key(ticket: str | None) -> str:
    """PROJ-123 -> PROJ (mirrors the console's project grouping)."""
    s = (ticket or "").strip()
    return s.rsplit("-", 1)[0] if "-" in s else ""


def decide(enforced: list, ticket: str | None = None, team: str | None = None,
           work_type: str | None = None) -> dict:
    """Resolve one request against the cached enforced-programs list. 'block' wins
    over 'downgrade'; 'allow' when nothing matches. `enforced` is exactly the list
    the console returns under `enforced`."""
    proj = _project_key(ticket)
    matched = []
    for p in enforced or []:
        for m in (p.get("members") or []):
            st, sid = m.get("scope_type"), m.get("scope_id")
            if (st == "overall"
                    or (st == "team" and team and team == sid)
                    or (st == "class" and work_type and work_type == sid)
                    or (st == "project" and proj and proj == sid)):
                matched.append(p)
                break
    if not matched:
        return {"decision": "allow"}
    block = next((p for p in matched if (p.get("action") or "block") == "block"), None)
    chosen = block or matched[0]
    return {"decision": chosen.get("action") or "block",
            "program": chosen.get("name"), "floor_model": chosen.get("floor_model")}


def fetch_enforced(console_url: str | None, api_key: str | None, timeout: float = 3.0):
    """GET /api/v1/enforcement from the console → the `enforced` list, or None on any
    failure (so the caller keeps its last cached verdict — fail-open)."""
    api_key = api_key or os.environ.get("MODELPILOT_API_KEY")
    if not console_url or not api_key:
        return None
    try:
        import httpx
        r = httpx.get(f"{console_url.rstrip('/')}/api/v1/enforcement",
                      headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("enforced") or []
    except Exception:  # noqa: BLE001 — never break the gateway on a control-plane blip
        return None
