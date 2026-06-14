"""Reliability: retry transient upstream failures and fall back to a more
capable model when a routed (cheaper) model errors. Pure decision logic so it's
testable without the network; the proxy/gateway drive the actual sends.

Stdlib-only (commodity — ships in the thin client).
"""

# Transient statuses worth retrying. 529 = Anthropic "overloaded".
RETRIABLE = frozenset({408, 409, 429, 500, 502, 503, 504, 529})

DEFAULT_MAX_RETRIES = 2
DEFAULT_BASE = 0.5
DEFAULT_CAP = 8.0


def parse_retry_after(value) -> float | None:
    """Seconds from a Retry-After header (delta-seconds form). None if absent/odd."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def backoff_seconds(attempt: int, retry_after=None, base: float = DEFAULT_BASE,
                    cap: float = DEFAULT_CAP) -> float:
    """How long to wait before `attempt` (0-based). Honors Retry-After if given,
    else capped exponential. Deterministic (no jitter) for predictable behavior."""
    ra = parse_retry_after(retry_after)
    if ra is not None:
        return min(cap, ra)
    return min(cap, base * (2 ** attempt))


def plan(status: int, attempt: int, max_retries: int, routed_model: str,
         original_model: str, fallback: bool = True):
    """Decide the next attempt after a response with `status` on attempt `attempt`
    (0-based). Returns None to stop, or a dict {model, attempt, reason}.

    On the first retry, if the routed (cheaper) model differs from the one the
    caller asked for and `fallback` is on, we retry on the *original* model — the
    safe, most-available choice — so routing never costs you reliability."""
    if status not in RETRIABLE or attempt >= max_retries:
        return None
    if fallback and routed_model != original_model:
        return {"model": original_model, "attempt": attempt + 1, "reason": "fallback-to-original"}
    return {"model": routed_model, "attempt": attempt + 1, "reason": "retry"}
