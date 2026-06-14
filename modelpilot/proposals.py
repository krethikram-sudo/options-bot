"""Submit auto-derived per-customer tuning proposals to the hosted console for
vendor review/approval (Track A floors, Track C rules).

Privacy: only the *proposal* is sent — a category + proposed tiers (floors) or a
rule spec (name + lexical signals + target category) + aggregate stats. No prompt
text or outputs. The console also rejects payloads carrying sensitive keys.

Config: MODELPILOT_CONSOLE_URL + MODELPILOT_DEPLOYMENT_ID (as on the gateway).
"""

import os


def _target(console_url: str | None, deployment_id: str | None) -> tuple[str, str]:
    url = (console_url or os.environ.get("MODELPILOT_CONSOLE_URL", "")).rstrip("/")
    dep = deployment_id or os.environ.get("MODELPILOT_DEPLOYMENT_ID", "")
    return url, dep


def _post(url: str, payload: dict, post_fn=None) -> bool:
    if post_fn is not None:
        post_fn(payload)
        return True
    import httpx
    headers = {}
    key = os.environ.get("MODELPILOT_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    r = httpx.post(f"{url}/api/proposals", json=payload, timeout=5.0, headers=headers)
    r.raise_for_status()
    return True


def submit_floor(category: str, current_tier: int, proposed_tier: int, samples: int,
                 non_inferior_rate: float, console_url: str | None = None,
                 deployment_id: str | None = None, post_fn=None) -> bool:
    url, dep = _target(console_url, deployment_id)
    if not url or not dep:
        return False
    return _post(url, {"deployment_id": dep, "kind": "floor", "category": category,
                       "payload": {"current_tier": current_tier, "proposed_tier": proposed_tier},
                       "stats": {"samples": samples, "non_inferior_rate": non_inferior_rate}},
                 post_fn)


def submit_floor_details(details: dict, console_url: str | None = None,
                         deployment_id: str | None = None, only_lowered: bool = True,
                         post_fn=None) -> int:
    """Submit floor proposals from learn_floors()['details']. Returns count sent."""
    n = 0
    for category, d in (details or {}).items():
        if only_lowered and not d.get("lowered"):
            continue
        if submit_floor(category, d["current_tier"], d["proposed_tier"],
                        int(d.get("samples", 0)), float(d.get("non_inferior_rate", 0.0)),
                        console_url, deployment_id, post_fn):
            n += 1
    return n


def submit_rule(rule: dict, samples: int = 0, console_url: str | None = None,
                deployment_id: str | None = None, post_fn=None) -> bool:
    url, dep = _target(console_url, deployment_id)
    category = rule.get("category")
    if not url or not dep or not category:
        return False
    payload = {k: rule[k] for k in ("name", "any", "regex", "max_tier")
               if k in rule and rule[k] not in (None, [])}
    payload["category"] = category
    return _post(url, {"deployment_id": dep, "kind": "rule", "category": category,
                       "payload": payload, "stats": {"samples": samples}}, post_fn)


def submit_rules(rules: list[dict], console_url: str | None = None,
                 deployment_id: str | None = None, post_fn=None) -> int:
    """Submit rule proposals (only those with a category filled in)."""
    n = 0
    for r in rules or []:
        samples = int(round((r.get("_seen_in_pct") or 0)))  # carried by the scaffold
        if submit_rule(r, samples, console_url, deployment_id, post_fn):
            n += 1
    return n
