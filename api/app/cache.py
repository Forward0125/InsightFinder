"""In-memory LRU + TTL cache for the /search/answer endpoint.

Caches the full event list per (query, mode, top_k, candidates) tuple
for 1 hour, max 200 entries. On hit, the cached events stream back
instantly, saving ~3.5 s of OpenAI calls per repeat query.

Trade-offs for the demo:
- Cache hits do NOT write a fresh ``queries`` row to Postgres, so the
  dashboard's "queries_total" counter undercounts repeated views.
- Cache hits replay the original query_id on the SSE ``done`` event
  (frontend doesn't use it for anything observable).
- Cache is per-process and resets on Render redeploy.

For the portfolio demo this trade-off is fine: recruiters click the
same handful of example queries repeatedly and the latency win is
worth the small dashboard inconsistency.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any


class TTLLRUCache:
    """In-memory LRU with absolute TTL on each entry. Thread-safe."""

    def __init__(self, max_entries: int, ttl_seconds: float) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits   = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                self._misses += 1
                return None
            ts, value = entry
            if time.monotonic() - ts > self.ttl_seconds:
                self._items.pop(key, None)
                self._misses += 1
                return None
            self._items.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
            self._items[key] = (time.monotonic(), value)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "entries":     len(self._items),
                "hits":        self._hits,
                "misses":      self._misses,
                "max_entries": self.max_entries,
                "ttl_seconds": int(self.ttl_seconds),
            }


def make_key(query: str, mode: str, top_k: int, candidates: int) -> str:
    """Stable cache key. Whitespace + case-insensitive on the query."""
    norm = (query or "").strip().lower()
    h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
    return f"{mode}:{top_k}:{candidates}:{h}"


# Module singleton.
answer_cache = TTLLRUCache(max_entries=200, ttl_seconds=3600.0)
