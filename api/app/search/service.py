"""Public ``search()`` orchestrator.

Modes:
    "bm25"          BM25 only (no embedding call)
    "dense"         dense only
    "hybrid"        BM25 + dense -> reciprocal rank fusion (no rerank)
    "hybrid_rerank" hybrid + cross-encoder rerank to top_k

For hybrid modes we retrieve ``candidates`` (default 50) per ranker
before fusion. The reranker runs over the fused candidates and returns
``top_k``.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

from app import db
from app.ingest.embed import embed_query
from app.logging import get_logger
from app.search.rerank import is_available as rerank_available, rerank
from app.search.retrieve import (
    Hit,
    bm25_search,
    dense_search,
    reciprocal_rank_fusion,
)


log = get_logger(__name__)


SearchMode = Literal["bm25", "dense", "hybrid", "hybrid_rerank"]


@dataclass
class SearchResult:
    query:       str
    mode:        SearchMode
    hits:        list[Hit]
    latency_ms:  dict[str, int]


async def search(
    query: str,
    *,
    mode: SearchMode = "hybrid_rerank",
    top_k: int = 10,
    candidates: int = 50,
) -> SearchResult:
    """Run retrieval according to ``mode`` and return top_k hits."""
    started = time.perf_counter()
    timings: dict[str, int] = {}

    # ─── Dense path needs the query embedding ───────────────────
    query_vec: list[float] | None = None
    if mode in ("dense", "hybrid", "hybrid_rerank"):
        t0 = time.perf_counter()
        query_vec = await embed_query(query)
        timings["embed_ms"] = int((time.perf_counter() - t0) * 1000)

    pool = await db.init_pool()

    if mode == "bm25":
        t0 = time.perf_counter()
        async with pool.acquire() as conn:
            hits = await bm25_search(conn, query, top_k)
        timings["bm25_ms"] = int((time.perf_counter() - t0) * 1000)

    elif mode == "dense":
        t0 = time.perf_counter()
        assert query_vec is not None
        async with pool.acquire() as conn:
            hits = await dense_search(conn, query_vec, top_k)
        timings["dense_ms"] = int((time.perf_counter() - t0) * 1000)

    else:  # hybrid or hybrid_rerank
        assert query_vec is not None

        # asyncpg connections aren't shareable across concurrent queries,
        # so each branch acquires its own. The pool has min_size=1
        # max_size=10, so two slots are always available.
        async def _bm25() -> list[Hit]:
            async with pool.acquire() as c:
                return await bm25_search(c, query, candidates)

        async def _dense() -> list[Hit]:
            async with pool.acquire() as c:
                assert query_vec is not None
                return await dense_search(c, query_vec, candidates)

        t0 = time.perf_counter()
        bm25_hits, dense_hits = await asyncio.gather(_bm25(), _dense())
        timings["retrieve_ms"] = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        fused = reciprocal_rank_fusion([bm25_hits, dense_hits])
        timings["fuse_ms"] = int((time.perf_counter() - t0) * 1000)
        hits = fused[:candidates]

    if mode == "hybrid_rerank":
        if rerank_available():
            t0 = time.perf_counter()
            hits = await rerank(query, hits, top_k=top_k)
            timings["rerank_ms"] = int((time.perf_counter() - t0) * 1000)
        else:
            # Graceful fallback in environments where sentence-transformers
            # isn't installed (prod) or has been disabled. The frontend
            # toggle still "works", just resolves to plain hybrid.
            log.info("search.rerank_unavailable_fallback")
            hits = hits[:top_k]
            timings["rerank_ms"] = 0
    elif mode == "hybrid":
        hits = hits[:top_k]
    # bm25 / dense modes already truncated to top_k.

    timings["total_ms"] = int((time.perf_counter() - started) * 1000)
    log.info("search.done", mode=mode, query=query, hits=len(hits), **timings)

    return SearchResult(query=query, mode=mode, hits=hits, latency_ms=timings)
