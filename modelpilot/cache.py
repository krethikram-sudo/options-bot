"""Exact-match response cache for the proxy — identical requests return a stored
response instantly, at zero upstream cost. Opt-in, in-process, and entirely on
your machine (cached responses never leave your box).

Keyed on the caller's original request body (so it hits regardless of how the
request would be routed). Streaming responses are not cached. Commodity,
stdlib-only — ships in the thin client.
"""

import hashlib
import json
import math
import threading
import time

DEFAULT_TTL = 600.0     # seconds
DEFAULT_MAX = 500       # entries
DEFAULT_SIM = 0.95      # semantic match threshold (cosine)


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


def cosine(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class SemanticCache:
    """Near-duplicate cache: serve a stored response when a new request's
    embedding is within `threshold` cosine of a cached one (same model bucket).
    Embeddings are supplied by the caller (the proxy, via a customer-configured
    endpoint) — this class is pure data + similarity, stdlib only. Cached
    responses stay local."""

    def __init__(self, ttl: float = DEFAULT_TTL, maxsize: int = 200,
                 threshold: float = DEFAULT_SIM):
        self.ttl = ttl
        self.maxsize = max(1, maxsize)
        self.threshold = threshold
        self._entries: list = []   # [ts, vector, content, ctype, bucket]
        self._lock = threading.Lock()

    def get(self, vector, bucket: str = "", now: float | None = None):
        now = now or time.time()
        best, best_sim = None, self.threshold
        with self._lock:
            self._entries = [e for e in self._entries if now - e[0] <= self.ttl]
            for e in self._entries:
                if e[4] != bucket:
                    continue
                sim = cosine(vector, e[1])
                if sim >= best_sim:
                    best_sim, best = sim, (e[2], e[3])
        return best

    def put(self, vector, content: bytes, content_type: str = "application/json",
            bucket: str = "", now: float | None = None) -> None:
        now = now or time.time()
        with self._lock:
            if len(self._entries) >= self.maxsize:
                self._entries.pop(0)
            self._entries.append([now, vector, content, content_type, bucket])

    def __len__(self) -> int:
        return len(self._entries)
