"""Daily OpenAI spend tracker (in-memory, per process).

Resets at UTC midnight. Used by /search/answer and the ingestion
pipeline as a hard floor on runaway costs in the public demo.

Not durable across restarts -- a redeploy resets the counter. For a
public single-instance demo that's acceptable; for multi-instance
scale-out, swap to Redis with TTL'd keys.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)


class SpendTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._date: str = ""
        self._spent_usd: float = 0.0

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_roll(self) -> None:
        today = self._today()
        if today != self._date:
            if self._date:
                log.info(
                    "spend.day_rolled",
                    previous_date=self._date,
                    previous_total_usd=round(self._spent_usd, 4),
                )
            self._date = today
            self._spent_usd = 0.0

    def remaining(self) -> float:
        """USD remaining in today's budget. May be negative if we ran over."""
        with self._lock:
            self._maybe_roll()
            return settings.daily_spend_cap_usd - self._spent_usd

    def under_cap(self) -> bool:
        return self.remaining() > 0.0

    def add(self, usd: float) -> float:
        """Record spend; returns new total for today."""
        with self._lock:
            self._maybe_roll()
            self._spent_usd += max(0.0, usd)
            total = self._spent_usd
        if total > settings.daily_spend_cap_usd:
            log.warning(
                "spend.over_cap",
                total_usd=round(total, 4),
                cap_usd=settings.daily_spend_cap_usd,
            )
        return total

    def snapshot(self) -> dict:
        with self._lock:
            self._maybe_roll()
            return {
                "date":         self._date,
                "spent_usd":    round(self._spent_usd, 6),
                "cap_usd":      settings.daily_spend_cap_usd,
                "remaining":    round(settings.daily_spend_cap_usd - self._spent_usd, 6),
            }


# One tracker per process.
tracker = SpendTracker()
