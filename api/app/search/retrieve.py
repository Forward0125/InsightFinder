"""BM25 + dense retrieval, plus reciprocal-rank fusion.

BM25 uses Postgres FTS via ``websearch_to_tsquery`` (Google-like syntax:
quoted phrases, OR, NOT). Ranking via ``ts_rank_cd``.

Dense uses pgvector's cosine distance (``<=>``) against the HNSW index
we created in step 4. We return ``1 - distance`` so higher = better
(matches BM25 sense).

Both queries join through ``documents`` -> ``companies`` so each hit
carries the source metadata the UI needs for citation chips.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import asyncpg
import numpy as np


# ─── Hit ────────────────────────────────────────────────────────


@dataclass
class Hit:
    """One retrieved chunk with source + per-stage scores."""
    chunk_id:           int
    document_id:        int
    chunk_index:        int
    text:               str
    token_count:        int | None
    ticker:             str
    filing_type:        str
    period_of_report:   str
    accession_number:   str

    # Scores -- only set by the stage that produced them.
    bm25_score:    float | None = None
    dense_score:   float | None = None
    fused_score:   float | None = None
    rerank_score:  float | None = None

    # Internal: position in the original ranked list it came from.
    bm25_rank:    int | None = None
    dense_rank:   int | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


def _row_to_hit(row: asyncpg.Record) -> Hit:
    return Hit(
        chunk_id=row["chunk_id"],
        document_id=row["document_id"],
        chunk_index=row["chunk_index"],
        text=row["text"],
        token_count=row["token_count"],
        ticker=row["ticker"],
        filing_type=row["filing_type"],
        period_of_report=row["period_of_report"].isoformat(),
        accession_number=row["accession_number"],
    )


# ─── BM25 ───────────────────────────────────────────────────────

_BM25_SQL = """
SELECT
    c.id           AS chunk_id,
    c.document_id  AS document_id,
    c.chunk_index  AS chunk_index,
    c.text         AS text,
    c.token_count  AS token_count,
    ts_rank_cd(c.tsv, query.q) AS bm25_score,
    co.ticker, d.filing_type, d.period_of_report, d.accession_number
FROM chunks c
CROSS JOIN websearch_to_tsquery('english', $1) AS query(q)
JOIN documents d  ON d.id  = c.document_id
JOIN companies co ON co.id = d.company_id
WHERE c.tsv @@ query.q
ORDER BY ts_rank_cd(c.tsv, query.q) DESC
LIMIT $2;
"""


async def bm25_search(
    conn: asyncpg.Connection, query: str, k: int
) -> list[Hit]:
    rows = await conn.fetch(_BM25_SQL, query, k)
    hits = []
    for rank, row in enumerate(rows, start=1):
        hit = _row_to_hit(row)
        hit.bm25_score = float(row["bm25_score"])
        hit.bm25_rank = rank
        hits.append(hit)
    return hits


# ─── Dense ──────────────────────────────────────────────────────

_DENSE_SQL = """
SELECT
    c.id           AS chunk_id,
    c.document_id  AS document_id,
    c.chunk_index  AS chunk_index,
    c.text         AS text,
    c.token_count  AS token_count,
    1 - (c.embedding <=> $1) AS dense_score,
    co.ticker, d.filing_type, d.period_of_report, d.accession_number
FROM chunks c
JOIN documents d  ON d.id  = c.document_id
JOIN companies co ON co.id = d.company_id
ORDER BY c.embedding <=> $1
LIMIT $2;
"""


async def dense_search(
    conn: asyncpg.Connection,
    query_vector: list[float] | np.ndarray,
    k: int,
) -> list[Hit]:
    vec = np.asarray(query_vector, dtype=np.float32)
    rows = await conn.fetch(_DENSE_SQL, vec, k)
    hits = []
    for rank, row in enumerate(rows, start=1):
        hit = _row_to_hit(row)
        hit.dense_score = float(row["dense_score"])
        hit.dense_rank = rank
        hits.append(hit)
    return hits


# ─── Reciprocal Rank Fusion ──────────────────────────────────────


def reciprocal_rank_fusion(
    rankings: list[list[Hit]], *, k: int = 60
) -> list[Hit]:
    """Combine multiple ranked lists. Higher score = better.

    The standard RRF formula::

        rrf_score(d) = sum over rankings R of 1 / (k + rank_R(d))

    We carry the union of all per-stage scores forward so the API
    response can show ``bm25_score``, ``dense_score``, AND
    ``fused_score`` for every hit.
    """
    fused: dict[int, float] = {}
    merged: dict[int, Hit] = {}

    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)

            existing = merged.get(hit.chunk_id)
            if existing is None:
                merged[hit.chunk_id] = hit
            else:
                # Same chunk surfaced by both rankings -- carry forward
                # whichever per-stage score the new ranking provides.
                if hit.bm25_score is not None and existing.bm25_score is None:
                    existing.bm25_score = hit.bm25_score
                    existing.bm25_rank = hit.bm25_rank
                if hit.dense_score is not None and existing.dense_score is None:
                    existing.dense_score = hit.dense_score
                    existing.dense_rank = hit.dense_rank

    sorted_ids = sorted(fused.keys(), key=lambda i: fused[i], reverse=True)
    out = []
    for chunk_id in sorted_ids:
        h = merged[chunk_id]
        h.fused_score = fused[chunk_id]
        out.append(h)
    return out
