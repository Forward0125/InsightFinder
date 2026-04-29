"""Chunks -> OpenAI embeddings.

Uses the OpenAI Python SDK. Batches up to 64 inputs per request to
stay well under the 8192-token-per-input and 300k-token-per-request
limits. Embeddings come back in input order.
"""

from __future__ import annotations

import asyncio

from openai import AsyncOpenAI, OpenAI

from app.logging import get_logger
from app.settings import settings


log = get_logger(__name__)

# text-embedding-3-small pricing (Apr 2026): $0.02 per 1M tokens.
USD_PER_1M_TOKENS = 0.02

BATCH_SIZE = 64


def estimate_cost_usd(total_tokens: int) -> float:
    return (total_tokens / 1_000_000) * USD_PER_1M_TOKENS


def embed_texts(
    texts: list[str], *, model: str | None = None
) -> list[list[float]]:
    """Return one embedding vector per input text, preserving order."""
    if not texts:
        return []

    client = OpenAI(api_key=settings.openai_api_key)
    model = model or settings.embedding_model

    embeddings: list[list[float]] = []
    for offset in range(0, len(texts), BATCH_SIZE):
        batch = texts[offset:offset + BATCH_SIZE]
        log.info(
            "embed.batch",
            model=model,
            offset=offset,
            size=len(batch),
        )
        resp = client.embeddings.create(model=model, input=batch)
        embeddings.extend(d.embedding for d in resp.data)

    return embeddings


# Async client is cached so we don't re-establish HTTP/2 connections per query.
_async_client: AsyncOpenAI | None = None
_async_lock = asyncio.Lock()


async def embed_query(text: str, *, model: str | None = None) -> list[float]:
    """Embed a single search query. Async to avoid blocking the event loop."""
    global _async_client
    if _async_client is None:
        async with _async_lock:
            if _async_client is None:
                _async_client = AsyncOpenAI(api_key=settings.openai_api_key)

    model = model or settings.embedding_model
    resp = await _async_client.embeddings.create(model=model, input=[text])
    return resp.data[0].embedding
