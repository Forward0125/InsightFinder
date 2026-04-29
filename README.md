# InsightFinder

A production RAG (retrieval-augmented generation) search platform over SEC filings of public companies. Built as the flagship case study for the [TwilightCore](https://twilightcore.dev) portfolio.

## What it does

Three surfaces over a single RAG pipeline:

1. **Query** — ask any question about a company's 10-K / 10-Q filings; get a streaming answer with inline citations and live evaluation scores (faithfulness, relevance, hallucination risk).
2. **Pipelines** — visualize document ingestion as a DAG; watch chunking, embedding, and indexing progress in real time. Visitors can trigger fresh ingestion of small PDFs.
3. **Dashboard** — KPIs, query performance trends, eval-gate health, and system alerts computed from real query traffic.

## Corpus

Latest 10-K and 10-Q filings for: Apple, Microsoft, Google, Amazon, Tesla, Nvidia, Meta, Netflix.

All sourced from public [SEC EDGAR](https://www.sec.gov/edgar.shtml).

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15 (App Router), Tailwind, framer-motion, React Flow, Tremor, Recharts |
| Backend | FastAPI (Python 3.12+), asyncpg, structlog |
| Database | Postgres 16 + `pgvector` + Postgres FTS (BM25) |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| Reranker | Local cross-encoder `BAAI/bge-reranker-base` (sentence-transformers) |
| Generator | Claude Sonnet 4.6 |
| Eval | DeepEval / custom faithfulness + relevance + grounding checks |
| Deploy | Vercel (web) + Fly.io (api) + Neon Postgres |

## Project structure

```
insightfinder/
├── api/                # FastAPI backend (scaffolded in step 3)
├── web/                # Next.js frontend (scaffolded in step 5)
├── data/
│   ├── raw/            # Downloaded SEC PDFs (gitignored content)
│   └── processed/      # Cached chunks
├── scripts/            # SEC fetcher + utilities
├── docs/               # Architecture notes
├── docker-compose.yml  # Local Postgres + pgvector
└── .env.example        # Env template
```

## Getting started

### Prerequisites

- Docker Desktop (for Postgres + pgvector)
- Python 3.12+
- Node.js 20+
- API keys: OpenAI, Anthropic

### Setup (after step 5)

```bash
# 1. Copy env template and fill in API keys
cp .env.example .env

# 2. Start Postgres
docker compose up -d

# 3. Backend
cd api
uv sync                      # creates .venv and installs deps
uv run python run.py         # starts dev server on http://localhost:8000

# 4. Frontend (in a second terminal)
cd web
pnpm install
pnpm dev
```

Visit `http://localhost:3000`.

## Status

**Step 1 of 15** — project scaffold complete. See [`docs/ROADMAP.md`](./docs/ROADMAP.md) for what's next.
