"""In-memory IP rate limiter.

Defensive against the public-demo case where one visitor (or a bot)
could rip through OpenAI credits by spamming /pipelines/runs.

Not durable across process restarts. For a single-instance deploy
that's acceptable; for a multi-instance scale-out we'd swap to Redis.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class IPRateLimiter:
    """Sliding-window IP rate limit, thread-safe."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events     = max_events
        self.window_seconds = window_seconds
        self._records: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, ip: str) -> tuple[bool, int]:
        """Returns (allowed, remaining_after_this_event).

        If ``allowed`` is False, ``remaining`` is 0 and the count of
        recent events is at or above ``max_events``.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            q = self._records[ip]

            # Drop events outside the window.
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= self.max_events:
                return False, 0

            q.append(now)
            remaining = self.max_events - len(q)
            return True, remaining

    def peek(self, ip: str) -> int:
        """Return how many events are allowed for this IP right now."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._records[ip]
            while q and q[0] < cutoff:
                q.popleft()
            return max(0, self.max_events - len(q))


# Module-level singletons, one per protected endpoint.
pipeline_runs_limiter = IPRateLimiter(max_events=5,  window_seconds=3600.0)
search_answer_limiter = IPRateLimiter(max_events=30, window_seconds=3600.0)
