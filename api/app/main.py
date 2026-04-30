"""FastAPI application entry point.

Run locally:
    uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.api import dashboard, health, pipelines, search
from app.logging import configure_logging, get_logger
from app.settings import settings


configure_logging(json=False)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup: open DB pool. Shutdown: close it."""
    log.info("app.starting", version="0.1.0")
    await db.init_pool()
    log.info("app.ready")
    try:
        yield
    finally:
        log.info("app.stopping")
        await db.close_pool()
        log.info("app.stopped")


app = FastAPI(
    title="InsightFinder API",
    version="0.1.0",
    description="Backend for the InsightFinder RAG search platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(pipelines.router)
app.include_router(search.router)
app.include_router(dashboard.router)
