"""Streamed RAG answer generation, OpenAI-only.

Layered on top of ``app.search.service.search``: takes the top hits,
builds a numbered SOURCES prompt, calls ``gpt-4o-mini`` with
``stream=True``, parses ``[N]`` citation markers from the streamed
text, and writes a ``queries`` row + ``query_results`` rows so the
dashboard has real traffic data to display.

Public entry point:

    async for event in stream_answer(query, mode='hybrid', top_k=8):
        ...

Yields these events (each a dict ready to JSON-encode):

    {"type": "meta",  "sources": [...], "search_latency_ms": {...}, "model": "..."}
    {"type": "token", "text": "..."}      (many)
    {"type": "done",  "query_id": int, "cited": [int], "response_text": "...",
                      "tokens_in": int, "tokens_out": int, "cost_usd": float,
                      "latency_ms": {...}}
    {"type": "error", "error": "..."}
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app import db
from app.cache import answer_cache, make_key
from app.eval import evaluate, persist_eval
from app.logging import get_logger
from app.search.service import SearchMode, search
from app.settings import settings
from app.spend_tracker import tracker as spend_tracker


log = get_logger(__name__)


# ─── Pricing (USD per 1M tokens, Apr 2026) ───────────────────────

# Tuple is (input, output). Models not listed get $0 cost reported,
# which is fine for dev/test models.
PRICES_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":  (0.15,  0.60),
    "gpt-4o":       (2.50, 10.00),
    "gpt-5-mini":   (0.25,  2.00),
    "gpt-5":        (1.25, 10.00),
}


def calc_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    in_p, out_p = PRICES_USD_PER_1M.get(model, (0.0, 0.0))
    return (tokens_in * in_p + tokens_out * out_p) / 1_000_000


# ─── Prompts ─────────────────────────────────────────────────────


SYSTEM_PROMPT = """You are InsightFinder, an analyst answering questions \
about US public-company SEC filings (10-K and 10-Q).

Rules:
- Use ONLY the numbered SOURCES below to answer. If the answer isn't in the \
sources, say so directly. Do not guess or fall back on general knowledge.
- After every claim, cite the source number(s) in square brackets, e.g. \
"Revenue grew 15% [3]." Multiple supporting sources: "[1][2]".
- Prefer specific numbers, dates, and quotes from the filings over \
generalisations.
- Be concise -- usually 2-4 sentences. Add a longer paragraph only if the \
question genuinely calls for it.
- Do NOT add a "Sources:" section at the end. Inline citations are \
sufficient.
- Name the company and reporting period explicitly when context allows."""


def build_user_prompt(query: str, hits: list[Any]) -> str:
    """Compose the SOURCES + QUESTION user message."""
    lines: list[str] = ["SOURCES", ""]
    for i, h in enumerate(hits, start=1):
        header = (
            f"[{i}] {h.ticker} {h.filing_type} "
            f"(period {h.period_of_report}, chunk #{h.chunk_index})"
        )
        lines.append(header)
        # Trim very long chunks to keep the prompt budget reasonable.
        text = h.text.strip()
        if len(text) > 2400:
            text = text[:2400] + "..."
        lines.append(text)
        lines.append("")
    lines.append(f"QUESTION: {query.strip()}")
    return "\n".join(lines)


# ─── Citation parsing ────────────────────────────────────────────

_CITE_RE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")


def extract_cited(answer: str, max_n: int) -> set[int]:
    """Pull ``[1][2,3]`` style citations out of an answer.

    Returns the set of (1-indexed) source numbers actually referenced,
    filtered to the valid ``1..max_n`` range so the model can't cite
    a chunk that wasn't supplied.
    """
    cited: set[int] = set()
    for m in _CITE_RE.finditer(answer):
        for token in re.split(r"[,;\s]+", m.group(1)):
            if not token:
                continue
            try:
                n = int(token)
            except ValueError:
                continue
            if 1 <= n <= max_n:
                cited.add(n)
    return cited


# ─── Persistence ────────────────────────────────────────────────


async def _persist(
    *,
    query: str,
    mode: str,
    response_text: str,
    hits: list[Any],
    cited: set[int],
    timings: dict[str, int],
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    model: str,
) -> int:
    """Write queries + query_results rows. Returns query_id."""
    pool = await db.init_pool()
    async with pool.acquire() as conn, conn.transaction():
        query_id = await conn.fetchval(
            """
            INSERT INTO queries (
                pipeline_id, query_text, retrieval_mode,
                response_text, generator_model,
                latency_total_ms, latency_retrieval_ms,
                latency_rerank_ms, latency_generation_ms,
                tokens_in, tokens_out, cost_usd
            )
            VALUES (
                (SELECT id FROM pipelines WHERE slug = 'sec-filings'),
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
            )
            RETURNING id
            """,
            query,
            mode,
            response_text,
            model,
            timings.get("total_ms"),
            (timings.get("retrieve_ms") or timings.get("dense_ms")
             or timings.get("bm25_ms")),
            timings.get("rerank_ms"),
            timings.get("generate_ms"),
            tokens_in,
            tokens_out,
            cost_usd,
        )

        if hits:
            await conn.executemany(
                """
                INSERT INTO query_results (
                    query_id, chunk_id, rank,
                    dense_score, bm25_score, rerank_score, was_cited
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                [
                    (
                        query_id,
                        h.chunk_id,
                        i + 1,
                        h.dense_score,
                        h.bm25_score,
                        h.rerank_score,
                        (i + 1) in cited,
                    )
                    for i, h in enumerate(hits)
                ],
            )

    return query_id


# ─── Streaming generator ────────────────────────────────────────


# Reuse one client across requests so HTTP/2 and TLS get warmed up.
_async_openai: AsyncOpenAI | None = None


def _get_openai() -> AsyncOpenAI:
    global _async_openai
    if _async_openai is None:
        _async_openai = AsyncOpenAI(api_key=settings.openai_api_key)
    return _async_openai


def _hit_to_source(rank: int, h: Any) -> dict[str, Any]:
    """Trimmed source payload for the `meta` SSE event."""
    return {
        "rank":             rank,
        "chunk_id":         h.chunk_id,
        "ticker":           h.ticker,
        "filing_type":      h.filing_type,
        "period_of_report": h.period_of_report,
        "accession_number": h.accession_number,
        "chunk_index":      h.chunk_index,
        "text":             h.text,
        "bm25_score":       h.bm25_score,
        "dense_score":      h.dense_score,
        "fused_score":      h.fused_score,
        "rerank_score":     h.rerank_score,
    }


async def _stream_answer_inner(
    query: str,
    *,
    mode: SearchMode = "hybrid",
    top_k: int = 8,
    candidates: int = 30,
    model: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE-ready event dicts for a complete RAG answer."""
    overall_start = time.perf_counter()
    model = model or settings.generator_model

    # ─── Retrieval ──────────────────────────────────────────────
    try:
        result = await search(
            query, mode=mode, top_k=top_k, candidates=candidates,
        )
    except Exception as exc:
        log.error("answer.search_failed", error=str(exc))
        yield {"type": "error", "error": f"retrieval failed: {exc}"}
        return

    if not result.hits:
        yield {
            "type": "meta",
            "model": model,
            "mode": mode,
            "sources": [],
            "search_latency_ms": result.latency_ms,
        }
        yield {
            "type": "done",
            "query_id": None,
            "cited": [],
            "response_text": "",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
            "latency_ms": {
                **result.latency_ms,
                "generate_ms": 0,
                "total_ms": int((time.perf_counter() - overall_start) * 1000),
            },
            "message": "no relevant chunks in the corpus -- nothing to answer from",
        }
        return

    # ─── Meta event ─────────────────────────────────────────────
    sources_payload = [_hit_to_source(i + 1, h) for i, h in enumerate(result.hits)]
    yield {
        "type": "meta",
        "model": model,
        "mode": mode,
        "sources": sources_payload,
        "search_latency_ms": result.latency_ms,
    }

    # ─── Build prompt and stream the answer ─────────────────────
    user_prompt = build_user_prompt(query, result.hits)

    client = _get_openai()
    gen_start = time.perf_counter()

    full_text_parts: list[str] = []
    tokens_in = 0
    tokens_out = 0

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            stream=True,
            stream_options={"include_usage": True},
            temperature=0.0,
            max_tokens=800,
        )
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full_text_parts.append(delta.content)
                    yield {"type": "token", "text": delta.content}
            if chunk.usage:
                tokens_in = chunk.usage.prompt_tokens or 0
                tokens_out = chunk.usage.completion_tokens or 0
    except Exception as exc:
        log.error("answer.openai_failed", error=str(exc))
        yield {"type": "error", "error": f"generation failed: {exc}"}
        return

    response_text = "".join(full_text_parts)
    generate_ms = int((time.perf_counter() - gen_start) * 1000)

    # ─── Parse citations + cost ─────────────────────────────────
    cited = extract_cited(response_text, max_n=len(result.hits))
    cost = calc_cost(model, tokens_in, tokens_out)
    spend_tracker.add(cost)

    timings_full = {
        **result.latency_ms,
        "generate_ms": generate_ms,
        "total_ms": int((time.perf_counter() - overall_start) * 1000),
    }

    # ─── Persist ────────────────────────────────────────────────
    try:
        query_id = await _persist(
            query=query,
            mode=mode,
            response_text=response_text,
            hits=result.hits,
            cited=cited,
            timings=timings_full,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            model=model,
        )
    except Exception as exc:
        log.error("answer.persist_failed", error=str(exc))
        query_id = None

    yield {
        "type": "done",
        "query_id": query_id,
        "cited": sorted(cited),
        "response_text": response_text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(cost, 6),
        "latency_ms": timings_full,
    }

    # ─── Eval gates ─────────────────────────────────────────────
    # Run the LLM-as-judge after the user has already seen their
    # answer. Stays inside the same SSE stream so the frontend can
    # animate the scores in without opening a second connection.
    if query_id is None:
        return

    eval_start = time.perf_counter()
    try:
        eval_result = await evaluate(query, result.hits, response_text)
    except Exception as exc:
        log.error("answer.eval_failed", error=str(exc))
        yield {"type": "eval_failed", "error": str(exc)}
        return

    try:
        await persist_eval(query_id, eval_result)
    except Exception as exc:
        log.error("answer.eval_persist_failed", error=str(exc))

    # Surface gate failures to the dashboard's alerts feed.
    if not eval_result.gates_passed:
        from app.alerts import emit_alert
        await emit_alert(
            severity="warning",
            title=f"Eval gate failed for query #{query_id}",
            body=(
                f"fai={eval_result.faithfulness:.2f}  "
                f"rel={eval_result.answer_relevance:.2f}  "
                f"halo={eval_result.hallucination_risk:.2f}"
            ),
            source="eval",
            metadata={"query_id": query_id, "model": eval_result.evaluator_model},
        )

    eval_cost = calc_cost(
        eval_result.evaluator_model, eval_result.tokens_in, eval_result.tokens_out,
    )
    spend_tracker.add(eval_cost)
    yield {
        "type": "eval",
        "query_id": query_id,
        "faithfulness":       round(eval_result.faithfulness, 3),
        "answer_relevance":   round(eval_result.answer_relevance, 3),
        "hallucination_risk": round(eval_result.hallucination_risk, 3),
        "gates_passed":       eval_result.gates_passed,
        "reasoning":          eval_result.reasoning,
        "evaluator_model":    eval_result.evaluator_model,
        "tokens_in":          eval_result.tokens_in,
        "tokens_out":         eval_result.tokens_out,
        "cost_usd":           round(eval_cost, 6),
        "latency_ms":         int((time.perf_counter() - eval_start) * 1000),
    }


# ─── SSE helper used by the HTTP layer ──────────────────────────


def to_sse(event: dict[str, Any]) -> str:
    """Format a dict as an SSE message."""
    name = event.get("type", "message")
    data = json.dumps(event, default=str)
    return f"event: {name}\ndata: {data}\n\n"


# ─── Caching wrapper ────────────────────────────────────────────


async def stream_answer(
    query:      str,
    *,
    mode:       SearchMode = "hybrid",
    top_k:      int = 8,
    candidates: int = 30,
    model:      str | None = None,
):
    """Cache-aware wrapper around the real generator.

    On cache hit, replays the captured event list instantly (sub-50ms
    end-to-end). On miss, runs the full pipeline and stores the
    successful event sequence for future hits.

    See app/cache.py for the trade-off discussion (in particular: hits
    don't write a fresh queries row, so dashboard counters undercount
    cached views).
    """
    cache_key = make_key(query, mode, top_k, candidates)

    cached = answer_cache.get(cache_key)
    if cached is not None:
        log.info("answer.cache_hit", q=query[:60], mode=mode, n_events=len(cached))
        for event in cached:
            yield event
        return

    captured: list[dict[str, Any]] = []
    saw_done = False
    saw_error = False

    async for event in _stream_answer_inner(
        query, mode=mode, top_k=top_k, candidates=candidates, model=model,
    ):
        captured.append(event)
        if event.get("type") == "done" and event.get("query_id") is not None:
            saw_done = True
        if event.get("type") in ("error", "run.failed"):
            saw_error = True
        yield event

    # Only cache full successful runs that produced a real query_id.
    if saw_done and not saw_error:
        answer_cache.set(cache_key, captured)
        log.info("answer.cache_store", q=query[:60], mode=mode, n_events=len(captured))
