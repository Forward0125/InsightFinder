"""Dev server entry point.

Equivalent to::

    uvicorn app.main:app --reload --port 8000

but as a Python script so we can pass uvicorn options through argparse
without remembering CLI flags. Cross-platform — no special handling
required (asyncpg works with the default Windows event loop).

Usage:
    uv run python run.py             # autoreload (default)
    uv run python run.py --no-reload
    uv run python run.py --port 9000
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the InsightFinder API dev server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable autoreload (useful for production-style runs).",
    )
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,  # let our structlog setup own logging
    )


if __name__ == "__main__":
    main()
