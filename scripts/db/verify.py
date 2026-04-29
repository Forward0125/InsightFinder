"""
Verify Postgres connectivity and bootstrap the pgvector + pg_trgm extensions.

Reads DATABASE_URL from .env (or environment), connects, applies the init
SQL idempotently (CREATE EXTENSION IF NOT EXISTS), and round-trips a vector
literal to prove pgvector is loaded and operational.

Usage:
    python scripts/db/verify.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INIT_SQL = PROJECT_ROOT / "infra" / "postgres" / "init" / "01-extensions.sql"


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set (check .env)")
        return 1

    # Mask password in display output.
    safe_url = url
    if "@" in safe_url and ":" in safe_url.split("@")[0]:
        prefix, host = safe_url.split("@", 1)
        user = prefix.rsplit(":", 1)[0]
        safe_url = f"{user}:***@{host}"
    print(f"-> Connecting to {safe_url}")

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"   ok -- {version.split(',')[0]}")

            print(f"-> Applying {INIT_SQL.relative_to(PROJECT_ROOT)}")
            cur.execute(INIT_SQL.read_text())

            print("-> Installed extensions")
            cur.execute(
                "SELECT extname, extversion FROM pg_extension "
                "WHERE extname IN ('vector', 'pg_trgm') ORDER BY extname;"
            )
            for name, ver in cur.fetchall():
                print(f"   {name:<10} {ver}")

            print("-> Round-tripping a vector literal")
            cur.execute("SELECT '[1,2,3]'::vector AS sample;")
            sample = cur.fetchone()[0]
            print(f"   sample = {sample}")

            print("-> Cosine distance sanity check")
            cur.execute("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector AS d;")
            distance = cur.fetchone()[0]
            print(f"   cos_distance([1,0,0], [0,1,0]) = {distance}")

        conn.commit()

    print("\nPostgres + pgvector verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
