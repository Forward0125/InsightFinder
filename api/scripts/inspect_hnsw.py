"""Verify the HNSW + GIN indexes on chunks are configured for the right ops.

Usage:
    cd api && uv run python scripts/inspect_hnsw.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from app.settings import settings  # noqa: E402


QUERY = """
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'chunks'
ORDER BY indexname;
"""


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        rows = await conn.fetch(QUERY)
        for r in rows:
            print(f"-> {r['indexname']}")
            print(f"   {r['indexdef']}")
            print()
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
