"""Run the ingestion pipeline over every filing listed in
data/raw/_index.csv -- skipping ones already indexed.

Sequential by default. OpenAI embedding throughput is rarely the
bottleneck; serial keeps logs readable and database load predictable.

Usage:
    cd api
    uv run python scripts/ingest_all.py                 # all 32 filings
    uv run python scripts/ingest_all.py --tickers AAPL,MSFT
    uv run python scripts/ingest_all.py --force         # re-ingest
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

# Allow `from app.*` imports when run as a standalone script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Force UTF-8 stdout so SEC glyphs (checkboxes, em-dashes) don't crash.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import db                              # noqa: E402
from app.ingest.pipeline import (                # noqa: E402
    INDEX_CSV,
    PROJECT_ROOT,
    run_pipeline_inline,
)
from app.logging import configure_logging        # noqa: E402


async def already_ingested(accession: str) -> bool:
    """Check if a document with this accession has chunks in the DB."""
    async with db.get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT d.id, count(c.id) AS n
            FROM documents d LEFT JOIN chunks c ON c.document_id = d.id
            WHERE d.accession_number = $1
            GROUP BY d.id
            """,
            accession,
        )
    return bool(row and row["n"] and row["n"] > 0)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--tickers", default="",
        help="Comma-separated subset of tickers (default: all).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-ingest even if a document is already indexed.",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Stop after N filings (0 = all).",
    )
    args = parser.parse_args()

    configure_logging(json=False)

    if not INDEX_CSV.exists():
        print(f"ERROR: {INDEX_CSV.relative_to(PROJECT_ROOT)} missing -- run sec_fetch.py first.")
        return 1

    wanted = (
        {t.strip().upper() for t in args.tickers.split(",") if t.strip()}
        if args.tickers else None
    )

    with INDEX_CSV.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    rows.sort(key=lambda r: (r["ticker"], r["filing_type"], r["period_of_report"]))

    if wanted:
        rows = [r for r in rows if r["ticker"] in wanted]

    print(f"Index has {len(rows)} filings.\n")

    # Open the pool once for the whole run.
    await db.init_pool()

    n_done = 0
    n_skip = 0
    n_fail = 0
    total_chunks = 0
    total_tokens = 0
    total_cost = 0.0

    try:
        for i, row in enumerate(rows, 1):
            if args.limit and n_done >= args.limit:
                break

            local_path = PROJECT_ROOT / row["local_path"]
            label = f"[{i:>2}/{len(rows)}] {row['ticker']:<6} {row['filing_type']:<5} {row['period_of_report']}"

            if not args.force and await already_ingested(row["accession_number"]):
                print(f"{label}  ... already indexed, skipping")
                n_skip += 1
                continue

            try:
                result = await run_pipeline_inline(local_path, triggered_by="bulk")
            except Exception as exc:
                print(f"{label}  FAIL: {exc}")
                n_fail += 1
                continue

            print(
                f"{label}  ok  chunks={result.chunks:>4}  "
                f"tokens={result.total_tokens:>6}  "
                f"cost=${result.cost_usd:>6.4f}  "
                f"{result.total_seconds:>5.1f}s"
            )
            n_done += 1
            total_chunks += result.chunks
            total_tokens += result.total_tokens
            total_cost += result.cost_usd
    finally:
        await db.close_pool()

    print()
    print("-" * 60)
    print(f"Ingested: {n_done}    skipped: {n_skip}    failed: {n_fail}")
    print(f"Total chunks: {total_chunks:,}   tokens: {total_tokens:,}   cost: ${total_cost:.4f}")
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
