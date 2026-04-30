# ─────────────────────────────────────────────────────────────────
# InsightFinder API
#
# Single-stage build using uv for fast deps install. Sentence-
# transformers (the rerank model) is intentionally NOT installed --
# torch + the model exceed Render's 512MB free tier. The frontend's
# hybrid_rerank toggle falls back to hybrid when ENABLE_RERANK=false.
# ─────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# uv binary, copied directly from the published image. Pin a known-good
# version rather than `latest` so deploys are reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.4.18 /uv /uvx /bin/

WORKDIR /app

# Helpful Python defaults for containers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# 1) Install dependencies first so the layer is cacheable across
#    code-only changes. We omit dev tools and the rerank extra.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Copy the project and install it.
COPY app     ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

# Make the venv's binaries available without `uv run`.
ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

# Render injects $PORT. Default to 8000 for local docker run.
# alembic runs every boot -- migrations are idempotent.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
