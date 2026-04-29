"""DB operations for ``pipeline_runs`` and ``pipeline_steps``.

Every ingestion creates a run; each stage of the pipeline (extract,
chunk, embed, index) creates a step row that's updated as it
progresses. The Pipelines view in the frontend (step 13) reads from
these tables to draw the live DAG.
"""

from __future__ import annotations

import json
from typing import Any

from app import db


# Step names match the DAG nodes shown in the screenshot 02_2.webp.
STEP_NAMES = ("extract", "chunk", "embed", "index")


# ─── Pipeline (the knowledge-base config) ────────────────────────


DEFAULT_PIPELINE_SLUG = "sec-filings"
DEFAULT_PIPELINE_NAME = "SEC Filings"
DEFAULT_PIPELINE_DESC = (
    "10-K and 10-Q filings for AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, NFLX."
)


async def get_or_create_default_pipeline() -> int:
    """Return the default pipeline id, creating it on first call."""
    async with db.get_conn() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM pipelines WHERE slug = $1",
            DEFAULT_PIPELINE_SLUG,
        )
        if existing is not None:
            return existing
        return await conn.fetchval(
            """
            INSERT INTO pipelines (slug, name, description, is_demo, config)
            VALUES ($1, $2, $3, false, $4::jsonb)
            RETURNING id
            """,
            DEFAULT_PIPELINE_SLUG,
            DEFAULT_PIPELINE_NAME,
            DEFAULT_PIPELINE_DESC,
            json.dumps({"chunk_target_tokens": 500, "chunk_overlap_tokens": 50}),
        )


# ─── Runs ────────────────────────────────────────────────────────


async def create_run(pipeline_id: int, triggered_by: str = "admin") -> int:
    """Create a new pipeline_run with status='running'.

    Inserts the four step rows up front so the UI can render the full
    DAG even before any step starts.
    """
    async with db.get_conn() as conn:
        async with conn.transaction():
            run_id = await conn.fetchval(
                """
                INSERT INTO pipeline_runs (
                    pipeline_id, status, triggered_by, started_at
                )
                VALUES ($1, 'running', $2, NOW())
                RETURNING id
                """,
                pipeline_id,
                triggered_by,
            )
            await conn.executemany(
                """
                INSERT INTO pipeline_steps (run_id, name, status)
                VALUES ($1, $2, 'queued')
                """,
                [(run_id, name) for name in STEP_NAMES],
            )
    return run_id


async def complete_run(
    run_id: int,
    *,
    total_pages: int = 0,
    total_chunks: int = 0,
) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE pipeline_runs
               SET status = 'success',
                   finished_at = NOW(),
                   total_files = 1,
                   total_pages = $2,
                   total_chunks = $3
             WHERE id = $1
            """,
            run_id, total_pages, total_chunks,
        )


async def fail_run(run_id: int, error: str) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE pipeline_runs
               SET status = 'failed',
                   finished_at = NOW(),
                   error_message = $2
             WHERE id = $1
            """,
            run_id, error,
        )


async def get_run(run_id: int) -> dict | None:
    async with db.get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, pipeline_id, status, triggered_by,
                   started_at, finished_at, total_files,
                   total_pages, total_chunks, error_message,
                   created_at
            FROM pipeline_runs
            WHERE id = $1
            """,
            run_id,
        )
        if row is None:
            return None
        steps = await conn.fetch(
            """
            SELECT name, status, progress_pct, started_at, finished_at, metadata
            FROM pipeline_steps
            WHERE run_id = $1
            ORDER BY id
            """,
            run_id,
        )
    return {**dict(row), "steps": [dict(s) for s in steps]}


# ─── Steps ───────────────────────────────────────────────────────


async def start_step(run_id: int, name: str) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE pipeline_steps
               SET status = 'running',
                   started_at = NOW(),
                   progress_pct = 0
             WHERE run_id = $1 AND name = $2
            """,
            run_id, name,
        )


async def update_step_progress(
    run_id: int, name: str, progress_pct: int
) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE pipeline_steps
               SET progress_pct = $3
             WHERE run_id = $1 AND name = $2
            """,
            run_id, name, progress_pct,
        )


async def complete_step(
    run_id: int, name: str, metadata: dict[str, Any] | None = None
) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE pipeline_steps
               SET status = 'success',
                   progress_pct = 100,
                   finished_at = NOW(),
                   metadata = $3::jsonb
             WHERE run_id = $1 AND name = $2
            """,
            run_id, name, json.dumps(metadata or {}),
        )


async def fail_step(run_id: int, name: str, error: str) -> None:
    async with db.get_conn() as conn:
        await conn.execute(
            """
            UPDATE pipeline_steps
               SET status = 'failed',
                   finished_at = NOW(),
                   metadata = $3::jsonb
             WHERE run_id = $1 AND name = $2
            """,
            run_id, name, json.dumps({"error": error}),
        )
