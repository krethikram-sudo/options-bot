"""Expected-remaining-conversation-length model.

The cache-aware economics layer needs E[remaining turns | turns so far] to
price a mid-conversation model switch (PRODUCT_DESIGN.md §3). This estimates
it from the ledger's observed conversation lengths via mean residual life:

    E[L - t | L >= t]   over the empirical length distribution.

Falls back to a flat default until enough conversations have been observed,
and assumes a near-end conversation when t exceeds everything seen.
"""

import time

DEFAULT_REMAINING = 5.0
MIN_SESSIONS = 50
MIN_RESIDUAL_SAMPLES = 10
REFRESH_SECONDS = 300


class ContinuationModel:
    def __init__(self, ledger, default_remaining: float = DEFAULT_REMAINING,
                 min_sessions: int = MIN_SESSIONS, refresh_seconds: float = REFRESH_SECONDS):
        self._ledger = ledger
        self._default = default_remaining
        self._min_sessions = min_sessions
        self._refresh_seconds = refresh_seconds
        self._lengths: list[int] = []
        self._loaded_at = 0.0

    def _lengths_fresh(self) -> list[int]:
        now = time.monotonic()
        if now - self._loaded_at > self._refresh_seconds:
            self._lengths = self._ledger.session_lengths()
            self._loaded_at = now
        return self._lengths

    def expected_remaining(self, turns_so_far: int) -> float:
        """Expected number of turns still to come, including none.

        `turns_so_far` counts the current request, so a value of 1 asks:
        "given a conversation just started, how much longer does it run?"
        """
        lengths = self._lengths_fresh()
        if len(lengths) < self._min_sessions:
            return self._default
        t = max(turns_so_far, 1)
        residuals = [length - t for length in lengths if length >= t]
        if len(residuals) < MIN_RESIDUAL_SAMPLES:
            # Deeper than almost anything observed — likely wrapping up.
            return 1.0
        return sum(residuals) / len(residuals)
