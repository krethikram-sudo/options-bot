"""Exact-match response cache for the proxy — identical requests return a stored
response instantly, at zero upstream cost. Opt-in, in-process, and entirely on
your machine (cached responses never leave your box).

Keyed on the caller's original request body (so it hits regardless of how the
request would be routed). Streaming responses are not cached. Commodity,
stdlib-only — ships in the thin client.
"""

import hashlib
import json
import threading
import time

DEFAULT_TTL = 600.0     # seconds
DEFAULT_MAX = 500       # entries


def request_key(body: dict) -> str:
    """Stable key for an exact request (canonical JSON of the full body)."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class ResponseCache:
    """Tiny thread-safe TTL + capacity cache. Values are (content_bytes,
    content_type). Evicts the oldest entry when full."""

    def __init__(self, ttl: float = DEFAULT_TTL, maxsize: int = DEFAULT_MAX):
        self.ttl = ttl
        self.maxsize = max(1, maxsize)
        self._d: dict[str, tuple[float, bytes, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, now: float | None = None):
        now = now or time.time()
        with self._lock:
            entry = self._d.get(key)
            if not entry:
                return None
            ts, content, ctype = entry
            if now - ts > self.ttl:
                self._d.pop(key, None)
                return None
            return content, ctype

    def put(self, key: str, content: bytes, content_type: str = "application/json",
            now: float | None = None) -> None:
        now = now or time.time()
        with self._lock:
            if key not in self._d and len(self._d) >= self.maxsize:
                # evict the oldest by insertion order (dicts preserve it)
                self._d.pop(next(iter(self._d)), None)
            self._d[key] = (now, content, content_type)

    def __len__(self) -> int:
        return len(self._d)
