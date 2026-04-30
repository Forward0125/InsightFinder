"""Chunks + embeddings -> Postgres rows.

All upserts are idempotent: re-ingesting the same filing replaces its
chunks (we delete existing chunks for the document, then bulk-insert).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import asyncpg
import numpy as np

from app.logging import get_logger


log = get_logger(__name__)


@dataclass
class FilingMeta:
    """Metadata for a filing -- read from data/raw/_index.csv."""
    ticker:           str
    company_name:     str
    cik:              str
    filing_type:      str
    accession_number: str
    filing_date:      str         # ISO date string
    period_of_report: str         # ISO date string
    primary_document: str
    source_url:       str
    local_path:       str         # repo-relative


async def upsert_company(conn: asyncpg.Connection, meta: FilingMeta) -> int:
    """Idempotent insert -- returns the company id."""
    return await conn.fetchval(
        """
        INSERT INTO companies (ticker, name, cik)
        VALUES ($1, $2, $3)
        ON CONFLICT (ticker) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        meta.ticker, meta.company_name, meta.cik,
    )


def _as_date(value: str | date) -> date:
    """Parse an ISO date string ('2025-12-27') or pass through a date."""
    return value if isinstance(value, date) else date.fromisoformat(value)


async def upsert_document(
    conn: asyncpg.Connection,
    company_id: int,
    meta: FilingMeta,
    *,
    total_pages: int | None = None,
    title: str | None = None,
) -> int:
    """Idempotent insert -- returns the document id."""
    return await conn.fetchval(
        """
        INSERT INTO documents (
            company_id, filing_type, filing_date, period_of_report,
            title, source_url, accession_number, raw_path,
            total_pages, ingested_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        ON CONFLICT (accession_number) DO UPDATE SET
            ingested_at  = NOW(),
            raw_path     = EXCLUDED.raw_path,
            total_pages  = EXCLUDED.total_pages
        RETURNING id
        """,
        company_id,
        meta.filing_type,
        _as_date(meta.filing_date),
        _as_date(meta.period_of_report),
        title or f"{meta.ticker} {meta.filing_type} {meta.period_of_report}",
        meta.source_url,
        meta.accession_number,
        meta.local_path,
        total_pages,
    )


async def replace_chunks(
    conn: asyncpg.Connection,
    document_id: int,
    chunks: list[dict],
    *,
    pipeline_run_id: int | None = None,
) -> int:
    """Delete existing chunks for the document and bulk-insert new ones.

    ``chunks`` is a list of dicts with keys: text, token_count,
    embedding (list[float] or numpy array), metadata (dict).

    ``pipeline_run_id`` is stored on each chunk so listing queries
    (``/pipelines/{id}/runs``) can join chunks back to the run that
    produced them and surface a file_label.

    Wraps everything in a single transaction so a failure mid-insert
    doesn't leave the document in a half-indexed state.
    """
    rows = [
        (
            document_id,
            pipeline_run_id,
            i,
            c["text"],
            c.get("token_count"),
            np.asarray(c["embedding"], dtype=np.float32),
            json.dumps(c.get("metadata") or {}),
        )
        for i, c in enumerate(chunks)
    ]

    async with conn.transaction():
        deleted = await conn.execute(
            "DELETE FROM chunks WHERE document_id = $1",
            document_id,
        )
        log.info("index.chunks_deleted", document_id=document_id, info=deleted)

        await conn.executemany(
            """
            INSERT INTO chunks (
                document_id, pipeline_run_id, chunk_index, text,
                token_count, embedding, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            """,
            rows,
        )
        log.info(
            "index.chunks_inserted",
            document_id=document_id,
            run_id=pipeline_run_id,
            n=len(rows),
        )

    return len(rows)
