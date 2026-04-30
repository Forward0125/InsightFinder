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

# Install dependencies. Cacheable across code-only changes.
# `--no-install-project` skips installing this repo as a package -- we
# don't need it (uvicorn finds `app.main:app` via WORKDIR + sys.path),
# and an editable install would trip on Hatchling's README check
# since .dockerignore omits the README from the build context.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App source.
COPY app     ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Make the venv's binaries available without `uv run`.
ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

# Render injects $PORT. Default to 8000 for local docker run.
# alembic runs every boot -- migrations are idempotent.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
