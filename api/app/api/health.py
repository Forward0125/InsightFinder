"""Health endpoint — proves the API is alive AND the DB is reachable."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import db
from app.cache import answer_cache
from app.logging import get_logger


log = get_logger(__name__)
router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str
    db: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness + readiness probe.

    Always returns 200 so a load balancer doesn't kill the pod just because
    the database is briefly unreachable. The frontend reads `db` to decide
    whether to show a degraded banner.
    """
    try:
        ok = await db.ping()
        return HealthResponse(status="ok", db="ok" if ok else "unreachable")
    except Exception as exc:
        log.warning("health.db_check_failed", error=str(exc))
        return HealthResponse(status="ok", db="unreachable")


@router.get("/cache/stats")
async def cache_stats() -> dict:
    """Visibility into the /search/answer result cache. Handy for
    confirming hit rate during a portfolio demo."""
    return answer_cache.stats()
