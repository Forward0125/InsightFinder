"""Async Postgres connection pool via asyncpg.

asyncpg works on every platform (including Windows with the default
ProactorEventLoop, where psycopg's async driver does not). It is also
the fastest async Postgres driver available for Python.

pgvector type adapters are registered on every fresh connection via the
pool's ``init`` callback, so ``vector`` columns are returned as numpy
arrays automatically.

Module-level state is intentional: there is exactly one pool per
process, owned by the FastAPI lifespan handler in ``app.main``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from pgvector.asyncpg import register_vector

from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Set up each new connection (called once per acquire)."""
    await register_vector(conn)


async def init_pool() -> asyncpg.Pool:
    """Create and open the connection pool. Idempotent."""
    global _pool
    if _pool is not None:
        return _pool

    log.info("db.pool.opening", url=_safe_url(settings.database_url))
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
        init=_init_connection,
        timeout=10.0,
        command_timeout=30.0,
    )
    log.info("db.pool.opened", min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    """Close the connection pool. Idempotent."""
    global _pool
    if _pool is None:
        return
    log.info("db.pool.closing")
    await _pool.close()
    _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the live pool. Raises if init_pool() was never called."""
    if _pool is None:
        raise RuntimeError("DB pool not initialized -- call init_pool() first")
    return _pool


@asynccontextmanager
async def get_conn() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection from the pool. Use as `async with get_conn() as c:`."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


async def ping() -> bool:
    """Round-trip a SELECT 1 -- used by /health."""
    async with get_conn() as conn:
        result = await conn.fetchval("SELECT 1;")
    return result == 1


def _safe_url(url: str) -> str:
    """Strip the password from a Postgres URL for safe logging."""
    if "@" not in url:
        return url
    prefix, host = url.split("@", 1)
    if ":" not in prefix:
        return url
    user = prefix.rsplit(":", 1)[0]
    return f"{user}:***@{host}"
