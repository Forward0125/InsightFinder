"""Cross-encoder rerank using a local sentence-transformers model.

The model (``BAAI/bge-reranker-base``, ~280 MB) is lazy-loaded on the
first reranking call. After that it stays in memory for the life of
the process. Predictions are run inside ``asyncio.to_thread`` so the
event loop isn't blocked while torch crunches.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from app.logging import get_logger
from app.settings import settings

if TYPE_CHECKING:
    from app.search.retrieve import Hit


log = get_logger(__name__)

_model = None
_lock = threading.Lock()


def _load_model():
    """Return the cross-encoder, loading it on first call."""
    global _model
    if _model is not None:
        return _model

    with _lock:
        if _model is not None:
            return _model

        # Maximize CPU usage. By default torch on Windows uses 1 thread
        # which is brutal for cross-encoder inference. set_num_threads
        # must be called BEFORE the first tensor op.
        import os

        import torch

        cpu_count = os.cpu_count() or 4
        torch.set_num_threads(cpu_count)

        from sentence_transformers import CrossEncoder
        log.info(
            "rerank.loading",
            model=settings.reranker_model,
            torch_threads=cpu_count,
        )
        _model = CrossEncoder(settings.reranker_model)
        log.info("rerank.loaded")
    return _model


def _rerank_sync(query: str, hits: list["Hit"], top_k: int) -> list["Hit"]:
    if not hits:
        return []

    model = _load_model()
    pairs = [[query, h.text] for h in hits]

    # CrossEncoder.predict returns a numpy array (or list) of scores.
    scores = model.predict(pairs, show_progress_bar=False)

    for hit, score in zip(hits, scores):
        hit.rerank_score = float(score)

    return sorted(hits, key=lambda h: h.rerank_score or 0.0, reverse=True)[:top_k]


async def rerank(
    query: str, hits: list["Hit"], top_k: int = 10
) -> list["Hit"]:
    """Async wrapper around the sync rerank -- runs torch in a worker thread."""
    return await asyncio.to_thread(_rerank_sync, query, hits, top_k)
