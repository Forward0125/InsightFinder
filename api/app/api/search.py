"""Search HTTP endpoint.

  POST /search
    body: { query, mode, top_k, candidates }
    -> { query, mode, hits[], latency_ms{} }
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.answer import stream_answer, to_sse
from app.search.service import SearchMode, search


router = APIRouter(tags=["search"])


# ─── Request / response schemas ──────────────────────────────────


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    mode:  SearchMode = "hybrid_rerank"
    top_k: int = Field(10, ge=1, le=50)
    candidates: int = Field(
        50, ge=10, le=200,
        description="How many to retrieve before fusion/rerank (hybrid modes).",
    )


class Source(BaseModel):
    ticker:           str
    filing_type:      str
    period_of_report: str
    accession_number: str


class SearchHit(BaseModel):
    rank:         int
    chunk_id:     int
    document_id:  int
    chunk_index:  int
    text:         str
    token_count:  int | None = None

    bm25_score:   float | None = None
    dense_score:  float | None = None
    fused_score:  float | None = None
    rerank_score: float | None = None

    source:       Source


class SearchResponse(BaseModel):
    query:      str
    mode:       Literal["bm25", "dense", "hybrid", "hybrid_rerank"]
    hits:       list[SearchHit]
    latency_ms: dict[str, int]


# ─── Endpoint ────────────────────────────────────────────────────


@router.post("/search", response_model=SearchResponse)
async def post_search(req: SearchRequest) -> SearchResponse:
    if req.mode not in ("bm25", "dense", "hybrid", "hybrid_rerank"):
        raise HTTPException(400, f"unknown mode: {req.mode}")

    result = await search(
        req.query,
        mode=req.mode,
        top_k=req.top_k,
        candidates=req.candidates,
    )

    hits = [
        SearchHit(
            rank=i + 1,
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            chunk_index=h.chunk_index,
            text=h.text,
            token_count=h.token_count,
            bm25_score=h.bm25_score,
            dense_score=h.dense_score,
            fused_score=h.fused_score,
            rerank_score=h.rerank_score,
            source=Source(
                ticker=h.ticker,
                filing_type=h.filing_type,
                period_of_report=h.period_of_report,
                accession_number=h.accession_number,
            ),
        )
        for i, h in enumerate(result.hits)
    ]

    return SearchResponse(
        query=result.query,
        mode=result.mode,
        hits=hits,
        latency_ms=result.latency_ms,
    )


# ─── Streaming RAG answer ───────────────────────────────────────


class AnswerRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    mode:  SearchMode = "hybrid"
    top_k: int = Field(8, ge=1, le=20)
    candidates: int = Field(30, ge=10, le=100)


@router.post("/search/answer")
async def post_search_answer(req: AnswerRequest, request: Request) -> StreamingResponse:
    """Stream a cited RAG answer as Server-Sent Events.

    Event types:
      - ``meta``  : sources + search-stage latency, sent before any token
      - ``token`` : one delta of the answer text (many of these)
      - ``done``  : final tally (query_id, cited[], cost, total latency)
      - ``error`` : something went wrong; client should stop reading
    """
    async def gen() -> AsyncGenerator[str, None]:
        try:
            async for event in stream_answer(
                req.query,
                mode=req.mode,
                top_k=req.top_k,
                candidates=req.candidates,
            ):
                if await request.is_disconnected():
                    return
                yield to_sse(event)
        except Exception as exc:
            yield to_sse({"type": "error", "error": str(exc)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
