# InsightFinder API

FastAPI backend for [InsightFinder](../README.md).

## Run

From the repo root, ensure `.env` is set up (see `../.env.example`), then:

```bash
cd api
uv sync                       # creates .venv and installs deps
uv run python run.py          # starts dev server with autoreload
```

`run.py` is a small wrapper around `uvicorn.run` that handles CLI args
without remembering uvicorn flags. Cross-platform — asyncpg works with
the default event loop on Windows, Linux, and macOS.

If `uv` is not on your `PATH` yet, run `python -m uv ...` instead.

Visit:
- [http://localhost:8000/docs](http://localhost:8000/docs) — Swagger UI
- [http://localhost:8000/health](http://localhost:8000/health) — liveness + DB check

## Layout

```
api/
├── pyproject.toml      # dependencies + ruff/pytest config
├── app/
│   ├── main.py         # FastAPI app + lifespan
│   ├── settings.py     # env-driven config (pydantic-settings)
│   ├── db.py           # async psycopg pool
│   ├── logging.py      # structlog setup
│   └── api/
│       └── health.py   # /health endpoint
└── tests/              # pytest suite
```

## Dev commands

```bash
uv run ruff check .                # lint
uv run ruff format .               # format
uv run pytest                      # tests
```

## Search

```bash
# Just retrieval -- ranked chunks, no generation
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "data center capital expenditures", "mode": "hybrid", "top_k": 5}'

# Cited RAG answer streamed as Server-Sent Events
curl -N -X POST http://localhost:8000/search/answer \
  -H "Content-Type: application/json" \
  -d '{"query": "What was Apple iPhone revenue in Q1 2026?", "mode": "hybrid", "top_k": 6}'
```

`/search/answer` emits these SSE events:

  - `meta` — sources + retrieval-stage latency
  - `token` — one delta of the answer (many of these)
  - `done` — query_id, cited[], tokens, cost, total latency
  - `error` — something went wrong

Modes:

| `mode`           | What runs                                  | Typical latency (warm) |
|------------------|---------------------------------------------|------------------------|
| `bm25`           | Postgres FTS only                           | ~100 ms                |
| `dense`          | OpenAI embed + pgvector HNSW                | ~700 ms                |
| `hybrid`         | BM25 + dense in parallel + RRF              | ~700 ms                |
| `hybrid_rerank`  | hybrid + local cross-encoder (`MiniLM-L6`)  | 8–16 s on CPU          |

The reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`) is lazy-loaded on
first use (~5–10 s download + load). Subsequent calls reuse the
in-memory model. On CPU the rerank step dominates total latency; the
default UI surface should use `hybrid` mode and treat `hybrid_rerank`
as an opt-in "high quality" toggle.

## Migrations

Alembic with hand-written raw-SQL migrations (no SQLAlchemy ORM).

```bash
uv run alembic upgrade head           # apply all pending migrations
uv run alembic downgrade -1           # roll back one migration
uv run alembic current                # show current revision
uv run alembic history                # list all revisions
uv run alembic revision -m "name"     # create new migration file (raw-SQL only)
```

After running `alembic upgrade head`, sanity-check the schema:

```bash
uv run python scripts/inspect_schema.py
```
