"""Verify what's been ingested so far -- companies, documents, chunks.

Usage:
    cd api && uv run python scripts/inspect_ingestion.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Windows cp1252 console can't print every Unicode char that lands in
# SEC filings (e.g. checkbox glyphs). Force UTF-8 so we don't crash.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg                              # noqa: E402
from pgvector.asyncpg import register_vector  # noqa: E402

from app.settings import settings           # noqa: E402


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url)
    await register_vector(conn)
    try:
        print("=" * 70)
        print("COMPANIES")
        print("=" * 70)
        rows = await conn.fetch("SELECT id, ticker, name, cik FROM companies ORDER BY ticker;")
        for r in rows:
            print(f"  #{r['id']:<3} {r['ticker']:<6} {r['name']:<28} CIK={r['cik']}")
        print(f"  -> {len(rows)} companies\n")

        print("=" * 70)
        print("DOCUMENTS")
        print("=" * 70)
        docs = await conn.fetch("""
            SELECT d.id, c.ticker, d.filing_type, d.period_of_report, d.total_pages,
                   d.ingested_at,
                   (SELECT count(*) FROM chunks WHERE document_id = d.id) AS chunk_count
            FROM documents d JOIN companies c ON c.id = d.company_id
            ORDER BY d.ingested_at DESC NULLS LAST, c.ticker, d.filing_type, d.period_of_report DESC;
        """)
        for r in docs:
            ts = r['ingested_at'].strftime('%Y-%m-%d %H:%M') if r['ingested_at'] else '(not ingested)'
            print(
                f"  #{r['id']:<3} {r['ticker']:<6} {r['filing_type']:<5} "
                f"period={r['period_of_report']}  chunks={r['chunk_count']:>4}  "
                f"ingested={ts}"
            )
        print(f"  -> {len(docs)} documents\n")

        print("=" * 70)
        print("CHUNK STATS")
        print("=" * 70)
        stats = await conn.fetchrow("""
            SELECT
                count(*)                         AS n,
                avg(token_count)::int            AS avg_tokens,
                min(token_count)                 AS min_tokens,
                max(token_count)                 AS max_tokens,
                sum(token_count)                 AS total_tokens
            FROM chunks;
        """)
        print(f"  total chunks:  {stats['n']}")
        print(f"  avg tokens:    {stats['avg_tokens']}")
        print(f"  min tokens:    {stats['min_tokens']}")
        print(f"  max tokens:    {stats['max_tokens']}")
        print(f"  total tokens:  {stats['total_tokens']}\n")

        print("=" * 70)
        print("FIRST CHUNK SAMPLE")
        print("=" * 70)
        sample = await conn.fetchrow("""
            SELECT c.id, c.chunk_index, c.token_count,
                   substring(c.text, 1, 200) AS preview,
                   array_length(c.embedding::real[], 1) AS embedding_dim
            FROM chunks c
            ORDER BY c.id
            LIMIT 1;
        """)
        if sample:
            print(f"  id:            {sample['id']}")
            print(f"  chunk_index:   {sample['chunk_index']}")
            print(f"  token_count:   {sample['token_count']}")
            print(f"  embedding dim: {sample['embedding_dim']}")
            print(f"  preview:       {sample['preview']!r}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
