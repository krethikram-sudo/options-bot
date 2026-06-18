"""Tiny stdlib HTTP helper shared by the live pullers.

No new dependencies — `urllib.request` only. Every puller takes an optional
`transport` callable so tests (and offline runs) can inject canned responses
without touching the network or needing real admin credentials.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Optional

# transport(method, url, headers, body) -> parsed JSON dict
Transport = Callable[[str, str, dict, Optional[bytes]], dict]


def urllib_transport(
    method: str, url: str, headers: dict, body: Optional[bytes]
) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # surface the API's error body
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"{e.code} {e.reason} from {url}: {detail[:500]}") from e


def get_json(
    url: str, headers: dict, transport: Optional[Transport] = None
) -> dict:
    return (transport or urllib_transport)("GET", url, headers, None)


def post_json(
    url: str, headers: dict, payload: dict, transport: Optional[Transport] = None
) -> dict:
    body = json.dumps(payload).encode("utf-8")
    h = {**headers, "content-type": "application/json"}
    return (transport or urllib_transport)("POST", url, h, body)
