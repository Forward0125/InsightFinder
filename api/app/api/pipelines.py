"""Pipelines HTTP + SSE endpoints.

  POST /pipelines/runs                  -> kick off a run, return id
  GET  /pipelines/runs/{run_id}         -> current state (run + steps)
  GET  /pipelines/runs/{run_id}/events  -> SSE stream of live events
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ingest import pipeline, runs
from app.jobs import END_EVENT, broker
from app.logging import get_logger


log = get_logger(__name__)
router = APIRouter(prefix="/pipelines", tags=["pipelines"])


# ─── Schemas ─────────────────────────────────────────────────────


class CreateRunBody(BaseModel):
    """Visitor-triggered run on a specific filing already in data/raw/."""
    local_path: str = Field(
        ...,
        description="Repo-relative path to the .htm file, e.g. data/raw/AAPL/10-Q_*.htm",
        examples=["data/raw/AAPL/10-Q_2025-12-27_0000320193-26-000006.htm"],
    )


class CreateRunResponse(BaseModel):
    run_id: int


class StepInfo(BaseModel):
    name:         str
    status:       str
    progress_pct: int
    started_at:   Any | None = None
    finished_at:  Any | None = None
    metadata:     Any | None = None


class RunInfo(BaseModel):
    id:            int
    pipeline_id:   int
    status:        str
    triggered_by:  str | None = None
    started_at:    Any | None = None
    finished_at:   Any | None = None
    total_files:   int
    total_pages:   int
    total_chunks:  int
    error_message: str | None = None
    steps:         list[StepInfo]


# ─── Endpoints ───────────────────────────────────────────────────


@router.post("/runs", response_model=CreateRunResponse)
async def create_run(body: CreateRunBody) -> CreateRunResponse:
    """Start an ingestion run on a single filing."""
    path = (pipeline.PROJECT_ROOT / body.local_path).resolve()
    if not path.exists():
        raise HTTPException(404, f"file not found: {body.local_path}")
    if not str(path).startswith(str(pipeline.PROJECT_ROOT)):
        raise HTTPException(400, "path escapes project root")

    run_id = await pipeline.start_pipeline(path, triggered_by="api")
    log.info("run.created", run_id=run_id, path=body.local_path)
    return CreateRunResponse(run_id=run_id)


@router.get("/runs/{run_id}", response_model=RunInfo)
async def get_run(run_id: int) -> RunInfo:
    """Snapshot of run state (no streaming)."""
    row = await runs.get_run(run_id)
    if row is None:
        raise HTTPException(404, f"run {run_id} not found")
    # Coerce JSONB metadata that came back as str into dict for the response.
    for step in row["steps"]:
        meta = step.get("metadata")
        if isinstance(meta, str):
            try:
                step["metadata"] = json.loads(meta)
            except json.JSONDecodeError:
                pass
    return RunInfo(**row)


def _sse(event: dict[str, Any]) -> str:
    """Format a dict as an SSE message."""
    data = json.dumps(event, default=str)
    name = event.get("type", "message")
    return f"event: {name}\ndata: {data}\n\n"


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: int, request: Request) -> StreamingResponse:
    """Server-Sent Events stream of live pipeline progress for a run.

    On connect we replay the current run state (so a late subscriber
    isn't stuck waiting for the next event), then forward live events
    until ``stream.end`` is received or the client disconnects.
    """
    snapshot = await runs.get_run(run_id)
    if snapshot is None:
        raise HTTPException(404, f"run {run_id} not found")

    queue = broker.subscribe(run_id)

    async def event_gen() -> AsyncGenerator[str, None]:
        # Replay current state so the UI can paint the DAG immediately.
        yield _sse({
            "type": "snapshot",
            "run": {**snapshot, "steps": [
                # Don't re-encode JSONB strings.
                {**s, "metadata": _maybe_json(s.get("metadata"))}
                for s in snapshot["steps"]
            ]},
        })

        # Heartbeat every 15s so proxies don't kill the connection.
        try:
            while True:
                if await request.is_disconnected():
                    log.info("sse.client_disconnected", run_id=run_id)
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                if event is END_EVENT or event.get("type") == "stream.end":
                    yield _sse({"type": "stream.end"})
                    break

                yield _sse(event)
        finally:
            broker.unsubscribe(run_id, queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable buffering on nginx
            "Connection": "keep-alive",
        },
    )


def _maybe_json(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return v
    return v
