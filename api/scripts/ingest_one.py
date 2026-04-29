"""Run the ingestion pipeline on a single SEC filing.

Usage:
    cd api
    uv run python scripts/ingest_one.py <path-to-filing.htm>

    # Example:
    uv run python scripts/ingest_one.py ../data/raw/AAPL/10-K_2025-09-27_0000320193-25-000079.htm
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import asdict
from pathlib import Path

# Allow `from app.*` imports when run as a standalone script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db                         # noqa: E402
from app.ingest.pipeline import ingest_file  # noqa: E402
from app.logging import configure_logging    # noqa: E402


async def _run(path: Path) -> int:
    configure_logging(json=False)
    try:
        result = await ingest_file(path)
    finally:
        await db.close_pool()

    print()
    print("Ingestion summary")
    print("-" * 60)
    for k, v in asdict(result).items():
        print(f"  {k:<18} {v}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("path", type=Path, help="Path to a .htm filing.")
    args = parser.parse_args()

    return asyncio.run(_run(args.path.resolve()))


if __name__ == "__main__":
    sys.exit(main())
