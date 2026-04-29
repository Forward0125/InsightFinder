"""In-memory event broker for live pipeline progress.

Kept deliberately simple: the API process runs background jobs with
``asyncio.create_task``, and any number of SSE consumers can subscribe
to a run's queue. When the job finishes, the broker emits a sentinel
``{"type": "stream.end"}`` event so consumers cleanly close the stream.

Not durable across process restarts -- a visitor who reconnects mid-run
will see it via DB polling (``GET /pipelines/runs/{id}``), not via the
event stream.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


# Sentinel message that signals end-of-stream to SSE consumers.
END_EVENT: dict[str, Any] = {"type": "stream.end"}


class JobBroker:
    """Pub/sub for pipeline-run events, keyed by run_id."""

    def __init__(self) -> None:
        # One run can have many subscribers (e.g. visitor + admin both
        # watching). Each subscriber gets its own queue.
        self._subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, run_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers[run_id].append(q)
        return q

    def unsubscribe(self, run_id: int, queue: asyncio.Queue) -> None:
        try:
            self._subscribers[run_id].remove(queue)
        except (KeyError, ValueError):
            pass
        if not self._subscribers.get(run_id):
            self._subscribers.pop(run_id, None)

    async def emit(self, run_id: int, event: dict[str, Any]) -> None:
        """Broadcast an event to every subscriber of this run."""
        for q in list(self._subscribers.get(run_id, [])):
            # Drop on backpressure rather than block the producer.
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def end(self, run_id: int) -> None:
        """Send the end-of-stream sentinel and stop tracking this run."""
        await self.emit(run_id, END_EVENT)
        self._subscribers.pop(run_id, None)


# Module-level singleton -- one broker per process.
broker = JobBroker()
