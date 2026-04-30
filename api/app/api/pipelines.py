"""Pipelines HTTP + SSE endpoints.

  GET  /pipelines                       -> list configured pipelines
  GET  /pipelines/filings               -> filings available for ingestion
  GET  /pipelines/{id}/runs             -> recent runs for a pipeline
  POST /pipelines/runs                  -> kick off a run, return id
  GET  /pipelines/runs/{run_id}         -> current state (run + steps)
  GET  /pipelines/runs/{run_id}/events  -> SSE stream of live events
"""

from __future__ import annotations

import asyncio
import csv
import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import db
from app.ingest import pipeline, runs
from app.jobs import END_EVENT, broker
from app.logging import get_logger
from app.rate_limit import pipeline_runs_limiter


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


class RunListItem(BaseModel):
    id:           int
    status:       str
    triggered_by: str | None = None
    started_at:   Any | None = None
    finished_at:  Any | None = None
    total_chunks: int
    duration_ms:  int | None = None
    file_label:   str | None = None  # eg "AAPL 10-Q 2025-12-27"


class PipelineInfo(BaseModel):
    id:            int
    slug:          str
    name:          str
    description:   str | None = None
    is_demo:       bool
    runs_total:    int
    runs_running:  int
    runs_success:  int
    runs_failed:   int


class FilingChip(BaseModel):
    """One row of data/raw/_index.csv -- minus the noisy fields."""
    ticker:           str
    filing_type:      str
    period_of_report: str
    accession_number: str
    local_path:       str
    size_bytes:       int


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("", response_model=list[PipelineInfo])
async def list_pipelines() -> list[PipelineInfo]:
    """List configured pipelines (knowledge bases)."""
    async with db.get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.id, p.slug, p.name, p.description, p.is_demo,
                count(r.id)                                 AS runs_total,
                count(r.id) FILTER (WHERE r.status = 'running') AS runs_running,
                count(r.id) FILTER (WHERE r.status = 'success') AS runs_success,
                count(r.id) FILTER (WHERE r.status = 'failed')  AS runs_failed
            FROM pipelines p
            LEFT JOIN pipeline_runs r ON r.pipeline_id = p.id
            GROUP BY p.id
            ORDER BY p.id
            """,
        )
    return [PipelineInfo(**dict(r)) for r in rows]


@router.get("/filings", response_model=list[FilingChip])
async def list_filings() -> list[FilingChip]:
    """Filings available locally -- the source for the 'New Run' picker."""
    index_csv = pipeline.INDEX_CSV
    if not index_csv.exists():
        return []

    out: list[FilingChip] = []
    with index_csv.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(FilingChip(
                ticker=row["ticker"],
                filing_type=row["filing_type"],
                period_of_report=row["period_of_report"],
                accession_number=row["accession_number"],
                local_path=row["local_path"],
                size_bytes=int(row["size_bytes"]),
            ))
    out.sort(key=lambda f: (f.ticker, f.filing_type, f.period_of_report))
    return out


@router.get("/{pipeline_id}/runs", response_model=list[RunListItem])
async def list_pipeline_runs(
    pipeline_id: int,
    status: str | None = None,
    limit: int = 50,
) -> list[RunListItem]:
    """Recent runs for a pipeline, newest first."""
    if limit < 1 or limit > 200:
        raise HTTPException(400, "limit must be in 1..200")

    where = ["r.pipeline_id = $1"]
    params: list[Any] = [pipeline_id]
    if status:
        if status not in ("queued", "running", "success", "failed", "cancelled"):
            raise HTTPException(400, f"invalid status: {status}")
        params.append(status)
        where.append(f"r.status = ${len(params)}")

    params.append(limit)
    sql = f"""
        SELECT
            r.id, r.status, r.triggered_by,
            r.started_at, r.finished_at, r.total_chunks,
            EXTRACT(EPOCH FROM (r.finished_at - r.started_at)) * 1000 AS duration_ms,
            (
                SELECT co.ticker || ' ' || d.filing_type || ' ' || d.period_of_report::text
                FROM chunks c
                JOIN documents d  ON d.id  = c.document_id
                JOIN companies co ON co.id = d.company_id
                WHERE c.pipeline_run_id = r.id
                LIMIT 1
            ) AS file_label
        FROM pipeline_runs r
        WHERE {' AND '.join(where)}
        ORDER BY r.created_at DESC
        LIMIT ${len(params)}
    """

    async with db.get_conn() as conn:
        rows = await conn.fetch(sql, *params)
    return [
        RunListItem(
            id=r["id"], status=r["status"], triggered_by=r["triggered_by"],
            started_at=r["started_at"], finished_at=r["finished_at"],
            total_chunks=r["total_chunks"],
            duration_ms=int(r["duration_ms"]) if r["duration_ms"] is not None else None,
            file_label=r["file_label"],
        )
        for r in rows
    ]


@router.post("/runs", response_model=CreateRunResponse)
async def create_run(body: CreateRunBody, request: Request) -> CreateRunResponse:
    """Start an ingestion run on a single filing.

    Visitor-triggered. Throttled to 5 runs per IP per hour to prevent
    runaway OpenAI spend.
    """
    ip = request.client.host if request.client else "unknown"
    allowed, remaining = pipeline_runs_limiter.check(ip)
    if not allowed:
        raise HTTPException(
            429,
            "rate limit: 5 runs per hour per IP -- wait a bit and try again",
        )

    path = (pipeline.PROJECT_ROOT / body.local_path).resolve()
    if not path.exists():
        raise HTTPException(404, f"file not found: {body.local_path}")
    # Make sure the path is inside data/raw/ -- no walking up the tree.
    raw_root = (pipeline.PROJECT_ROOT / "data" / "raw").resolve()
    if not str(path).startswith(str(raw_root)):
        raise HTTPException(400, "path must be under data/raw/")

    run_id = await pipeline.start_pipeline(path, triggered_by="visitor")
    log.info(
        "run.created",
        run_id=run_id,
        path=body.local_path,
        ip=ip,
        rate_remaining=remaining,
    )
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
