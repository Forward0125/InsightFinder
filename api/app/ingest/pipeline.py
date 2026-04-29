"""Orchestrator -- runs extract -> chunk -> embed -> index for one file.

Step 7 keeps everything sync/in-process. Step 8 turns this into a
background job with state in pipeline_runs/pipeline_steps.
"""

from __future__ import annotations

import csv
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app import db
from app.ingest import embed, extract, index
from app.ingest.chunk import chunk_text
from app.ingest.index import FilingMeta
from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)

PROJECT_ROOT = Path(settings.database_url).parent if False else Path(__file__).resolve().parents[3]
INDEX_CSV = PROJECT_ROOT / "data" / "raw" / "_index.csv"

# Cost guard: prevents an accident from blowing up the OpenAI bill.
# At $0.02 / 1M tokens, 500k tokens = $0.01. Generous.
MAX_TOKENS_PER_DOC = 500_000


# ─── Result struct ───────────────────────────────────────────────


@dataclass
class IngestResult:
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


def lookup_meta(local_path: Path) -> FilingMeta:
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
                return FilingMeta(**{k: row[k] for k in FilingMeta.__dataclass_fields__})

    raise LookupError(f"no _index.csv row for {rel}")


# ─── Pipeline ────────────────────────────────────────────────────


async def ingest_file(local_path: Path) -> IngestResult:
    """Run extract -> chunk -> embed -> index on a single SEC filing."""
    started = time.perf_counter()

    if not local_path.exists():
        raise FileNotFoundError(local_path)

    meta = lookup_meta(local_path)
    log.info(
        "ingest.start",
        ticker=meta.ticker,
        filing_type=meta.filing_type,
        period=meta.period_of_report,
        path=str(local_path),
    )

    # 1. Extract ─────────────────────────────────────────────────
    t0 = time.perf_counter()
    text = extract.extract_file(local_path)
    extract_s = time.perf_counter() - t0
    log.info("ingest.extract.done", chars=len(text), seconds=round(extract_s, 2))

    # 2. Chunk ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    chunks = chunk_text(text)
    chunk_s = time.perf_counter() - t0
    total_tokens = sum(c.token_count for c in chunks)
    log.info(
        "ingest.chunk.done",
        chunks=len(chunks),
        tokens=total_tokens,
        seconds=round(chunk_s, 2),
    )

    if total_tokens > MAX_TOKENS_PER_DOC:
        raise ValueError(
            f"{local_path.name}: {total_tokens} tokens exceeds cost guard "
            f"{MAX_TOKENS_PER_DOC} -- raise MAX_TOKENS_PER_DOC if intentional."
        )

    if not chunks:
        raise ValueError(f"{local_path.name}: extracted 0 chunks -- empty doc?")

    # 3. Embed ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    vectors = embed.embed_texts([c.text for c in chunks])
    embed_s = time.perf_counter() - t0
    log.info(
        "ingest.embed.done",
        n=len(vectors),
        seconds=round(embed_s, 2),
        cost_usd=round(embed.estimate_cost_usd(total_tokens), 4),
    )

    # 4. Index ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    pool = await db.init_pool()
    async with pool.acquire() as conn:
        company_id = await index.upsert_company(conn, meta)
        document_id = await index.upsert_document(conn, company_id, meta)
        n_chunks = await index.replace_chunks(
            conn,
            document_id,
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
        )
    index_s = time.perf_counter() - t0
    log.info(
        "ingest.index.done",
        document_id=document_id,
        chunks=n_chunks,
        seconds=round(index_s, 2),
    )

    total_s = time.perf_counter() - started
    result = IngestResult(
        document_id=document_id,
        chunks=n_chunks,
        total_tokens=total_tokens,
        cost_usd=round(embed.estimate_cost_usd(total_tokens), 4),
        extract_seconds=round(extract_s, 2),
        chunk_seconds=round(chunk_s, 2),
        embed_seconds=round(embed_s, 2),
        index_seconds=round(index_s, 2),
        total_seconds=round(total_s, 2),
    )
    log.info("ingest.done", **asdict(result))
    return result
