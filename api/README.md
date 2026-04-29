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
