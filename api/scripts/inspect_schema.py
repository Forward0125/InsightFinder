"""Print all tables, their column counts, and any indexes -- a quick post-
migration smoke test.

Usage:
    cd api && uv run python scripts/inspect_schema.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `from app.*` imports when run as a standalone script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from app.settings import settings  # noqa: E402


SCHEMA_QUERY = """
SELECT
    c.relname  AS table_name,
    (SELECT count(*) FROM information_schema.columns
        WHERE table_name = c.relname AND table_schema = 'public') AS columns,
    (SELECT count(*) FROM pg_indexes WHERE tablename = c.relname AND schemaname = 'public') AS indexes
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname;
"""

INDEX_QUERY = """
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
"""

ENUM_QUERY = """
SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder) AS labels
FROM pg_type t
JOIN pg_enum e ON e.enumtypid = t.oid
GROUP BY t.typname
ORDER BY t.typname;
"""


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        print("=" * 60)
        print("TABLES")
        print("=" * 60)
        rows = await conn.fetch(SCHEMA_QUERY)
        for r in rows:
            print(f"  {r['table_name']:<20} {r['columns']:>3} cols, {r['indexes']:>2} indexes")
        print(f"\n  total: {len(rows)} tables")

        print("\n" + "=" * 60)
        print("INDEXES")
        print("=" * 60)
        rows = await conn.fetch(INDEX_QUERY)
        for r in rows:
            print(f"  {r['tablename']:<18} {r['indexname']}")

        print("\n" + "=" * 60)
        print("ENUMS")
        print("=" * 60)
        rows = await conn.fetch(ENUM_QUERY)
        for r in rows:
            print(f"  {r['typname']:<20} = {r['labels']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
