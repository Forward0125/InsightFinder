"""Orchestrator -- runs extract -> chunk -> embed -> index for one file.

Every ingestion creates a ``pipeline_run`` row plus four
``pipeline_steps`` rows (extract / chunk / embed / index) which the
frontend's Pipelines view subscribes to via SSE for live DAG
animation. Events are also broadcast through the in-memory
``JobBroker``.

Two entry points:

  - ``run_pipeline_inline(local_path)``: await full completion. Used by
    scripts. Caller must ensure the DB pool is initialized.
  - ``start_pipeline(local_path, ...)``: returns the run_id immediately
    after spawning a background task. Used by the HTTP endpoint.
"""

from __future__ import annotations

import asyncio
import csv
import time
from dataclasses import dataclass
from pathlib import Path

from app import db
from app.ingest import embed, extract, index, runs
from app.ingest.chunk import chunk_text
from app.ingest.embed import BATCH_SIZE as EMBED_BATCH_SIZE
from app.ingest.index import FilingMeta
from app.jobs import broker
from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)

# api/app/ingest/pipeline.py -> api/app/ingest -> api/app -> api -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
INDEX_CSV = PROJECT_ROOT / "data" / "raw" / "_index.csv"

# Cost guard. text-embedding-3-small at $0.02/1M tokens, 500k = $0.01.
MAX_TOKENS_PER_DOC = 500_000


# ─── Result struct ───────────────────────────────────────────────


@dataclass
class RunResult:
    run_id:          int
    document_id:     int
    chunks:          int
    total_tokens:    int
    cost_usd:        float
    extract_seconds: float
    chunk_seconds:   float
    embed_seconds:   float
    index_seconds:   float
    total_seconds:   float


# ─── Index lookup ────────────────────────────────────────────────


def _meta_for_path(local_path: Path) -> FilingMeta:
    """Find metadata for a filing in data/raw/_index.csv."""
    if not INDEX_CSV.exists():
        raise FileNotFoundError(
            f"{INDEX_CSV.relative_to(PROJECT_ROOT)} missing -- "
            "run scripts/sec_fetch.py first."
        )

    rel = str(local_path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")

    with INDEX_CSV.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["local_path"] == rel:
                return FilingMeta(
                    **{k: row[k] for k in FilingMeta.__dataclass_fields__}
                )

    raise LookupError(f"no _index.csv row for {rel}")


# ─── The pipeline body ───────────────────────────────────────────


async def _run_steps(run_id: int, local_path: Path) -> RunResult:
    """Execute the four pipeline steps, updating DB + emitting events."""
    started = time.perf_counter()
    meta = _meta_for_path(local_path)

    await broker.emit(run_id, {
        "type": "run.started",
        "run_id": run_id,
        "ticker": meta.ticker,
        "filing_type": meta.filing_type,
        "period": meta.period_of_report,
        "local_path": meta.local_path,
    })

    # 1. Extract ─────────────────────────────────────────────────
    await runs.start_step(run_id, "extract")
    await broker.emit(run_id, {"type": "step.started", "step": "extract"})

    t0 = time.perf_counter()
    text = extract.extract_file(local_path)
    extract_s = time.perf_counter() - t0

    await runs.complete_step(
        run_id, "extract",
        {"chars": len(text), "seconds": round(extract_s, 2)},
    )
    await broker.emit(run_id, {
        "type": "step.completed", "step": "extract",
        "chars": len(text), "seconds": round(extract_s, 2),
    })

    # 2. Chunk ──────────────────────────────────────────────────
    await runs.start_step(run_id, "chunk")
    await broker.emit(run_id, {"type": "step.started", "step": "chunk"})

    t0 = time.perf_counter()
    chunks = chunk_text(text)
    chunk_s = time.perf_counter() - t0

    if not chunks:
        raise ValueError(f"{local_path.name}: extracted 0 chunks -- empty doc?")

    total_tokens = sum(c.token_count for c in chunks)
    if total_tokens > MAX_TOKENS_PER_DOC:
        raise ValueError(
            f"{local_path.name}: {total_tokens} tokens exceeds cost guard "
            f"{MAX_TOKENS_PER_DOC} -- raise MAX_TOKENS_PER_DOC if intentional."
        )

    await runs.complete_step(
        run_id, "chunk",
        {"chunks": len(chunks), "tokens": total_tokens,
         "seconds": round(chunk_s, 2)},
    )
    await broker.emit(run_id, {
        "type": "step.completed", "step": "chunk",
        "chunks": len(chunks), "tokens": total_tokens,
        "seconds": round(chunk_s, 2),
    })

    # 3. Embed ──────────────────────────────────────────────────
    # Batched; emit progress per-batch so the UI can show a real bar.
    await runs.start_step(run_id, "embed")
    await broker.emit(run_id, {"type": "step.started", "step": "embed"})

    t0 = time.perf_counter()
    vectors: list[list[float]] = []
    n_batches = (len(chunks) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    for batch_idx, start in enumerate(range(0, len(chunks), EMBED_BATCH_SIZE)):
        batch_texts = [c.text for c in chunks[start:start + EMBED_BATCH_SIZE]]
        # embed_texts loops internally too, but we slice here so we can
        # update progress between batches. Call with a single batch:
        vectors.extend(embed.embed_texts(batch_texts))
        progress = int((batch_idx + 1) / n_batches * 100)
        await runs.update_step_progress(run_id, "embed", progress)
        await broker.emit(run_id, {
            "type": "step.progress", "step": "embed",
            "progress_pct": progress,
            "batch": batch_idx + 1, "batches": n_batches,
        })
    embed_s = time.perf_counter() - t0
    cost = round(embed.estimate_cost_usd(total_tokens), 4)

    await runs.complete_step(
        run_id, "embed",
        {"n": len(vectors), "seconds": round(embed_s, 2), "cost_usd": cost},
    )
    await broker.emit(run_id, {
        "type": "step.completed", "step": "embed",
        "n": len(vectors), "seconds": round(embed_s, 2), "cost_usd": cost,
    })

    # 4. Index ──────────────────────────────────────────────────
    await runs.start_step(run_id, "index")
    await broker.emit(run_id, {"type": "step.started", "step": "index"})

    t0 = time.perf_counter()
    pool = await db.init_pool()
    async with pool.acquire() as conn:
        company_id = await index.upsert_company(conn, meta)
        document_id = await index.upsert_document(conn, company_id, meta)
        n_chunks = await index.replace_chunks(
            conn, document_id,
            [
                {
                    "text":        c.text,
                    "token_count": c.token_count,
                    "embedding":   vectors[i],
                    "metadata":    {
                        **c.metadata,
                        "ticker":      meta.ticker,
                        "filing_type": meta.filing_type,
                    },
                }
                for i, c in enumerate(chunks)
            ],
            pipeline_run_id=run_id,
        )
    index_s = time.perf_counter() - t0

    await runs.complete_step(
        run_id, "index",
        {"document_id": document_id, "chunks": n_chunks,
         "seconds": round(index_s, 2)},
    )
    await broker.emit(run_id, {
        "type": "step.completed", "step": "index",
        "document_id": document_id, "chunks": n_chunks,
        "seconds": round(index_s, 2),
    })

    # Run done.
    total_s = time.perf_counter() - started
    await runs.complete_run(run_id, total_chunks=n_chunks)
    await broker.emit(run_id, {
        "type": "run.completed",
        "run_id": run_id, "document_id": document_id,
        "chunks": n_chunks, "tokens": total_tokens,
        "seconds": round(total_s, 2), "cost_usd": cost,
    })

    return RunResult(
        run_id=run_id,
        document_id=document_id,
        chunks=n_chunks,
        total_tokens=total_tokens,
        cost_usd=cost,
        extract_seconds=round(extract_s, 2),
        chunk_seconds=round(chunk_s, 2),
        embed_seconds=round(embed_s, 2),
        index_seconds=round(index_s, 2),
        total_seconds=round(total_s, 2),
    )


# ─── Public API ──────────────────────────────────────────────────


async def run_pipeline_inline(
    local_path: Path,
    *,
    pipeline_id: int | None = None,
    triggered_by: str = "admin",
) -> RunResult:
    """Run the pipeline, awaiting full completion. Use from scripts."""
    if pipeline_id is None:
        pipeline_id = await runs.get_or_create_default_pipeline()

    run_id = await runs.create_run(pipeline_id, triggered_by)

    try:
        return await _run_steps(run_id, local_path)
    except Exception as exc:
        # Mark whichever step is currently running as failed.
        run = await runs.get_run(run_id)
        if run:
            for step in run["steps"]:
                if step["status"] == "running":
                    await runs.fail_step(run_id, step["name"], str(exc))
                    break
        await runs.fail_run(run_id, str(exc))
        await broker.emit(run_id, {
            "type": "run.failed",
            "run_id": run_id,
            "error": str(exc),
        })
        log.error("pipeline.failed", run_id=run_id, error=str(exc))
        raise
    finally:
        await broker.end(run_id)


async def start_pipeline(
    local_path: Path,
    *,
    pipeline_id: int | None = None,
    triggered_by: str = "visitor",
) -> int:
    """Spawn the pipeline as a background task. Returns run_id immediately."""
    if pipeline_id is None:
        pipeline_id = await runs.get_or_create_default_pipeline()

    run_id = await runs.create_run(pipeline_id, triggered_by)

    async def _bg() -> None:
        try:
            await _run_steps(run_id, local_path)
        except Exception as exc:
            run = await runs.get_run(run_id)
            if run:
                for step in run["steps"]:
                    if step["status"] == "running":
                        await runs.fail_step(run_id, step["name"], str(exc))
                        break
            await runs.fail_run(run_id, str(exc))
            await broker.emit(run_id, {
                "type": "run.failed",
                "run_id": run_id,
                "error": str(exc),
            })
            log.error("pipeline.failed", run_id=run_id, error=str(exc))
        finally:
            await broker.end(run_id)

    asyncio.create_task(_bg())
    return run_id
