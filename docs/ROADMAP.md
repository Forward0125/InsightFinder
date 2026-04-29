# InsightFinder — Build Roadmap

15 sequenced steps from empty folder to deployed product.

## Foundation
- [x] **1. Scaffold project folder** — README, .gitignore, .env.example, docker-compose.yml, folder tree
- [x] **2. Postgres + pgvector running** — Neon connection verified, `vector` + `pg_trgm` extensions installed
- [x] **3. FastAPI backend skeleton** — settings, asyncpg pool, `/health` returns `{"status":"ok","db":"ok"}`
- [x] **4. Database schema + migrations** — 10 tables, HNSW + GIN indexes, 2 enums, applied via Alembic
- [x] **5. Next.js frontend skeleton** — Next 16 + Tailwind, design tokens from portfolio, 3 route shells, /health probe wired

## Ingestion
- [x] **6. SEC filing fetcher** — 32 filings (8 companies × 2 10-K + 2 10-Q), 76 MB cached locally, idempotent re-runs
- [x] **7. HTML → chunks pipeline (sync)** — extract (iXBRL noise stripped) → chunk (paragraph-aware, ≤500 tok) → embed → index. AAPL 10-Q: 44 chunks/$0.0003/6.7s; MSFT 10-K: 172 chunks/$0.0013/19s
- [ ] **8. Async pipeline + SSE progress** — background job, state in DB, live progress streaming

## Retrieval & Answer
- [ ] **9. Hybrid retrieval + local rerank** — `/search` returns ranked chunks (BM25 + dense + cross-encoder)
- [ ] **10. Streaming answer with citations** — Claude generates answer with `[1][2][3]` citations
- [ ] **11. Eval gates** — faithfulness, relevance, hallucination scoring per query

## Frontend (3 surfaces)
- [ ] **12. Query Detail View** — matches `02_1.webp`
- [ ] **13. Pipelines View** — matches `02_2.webp`
- [ ] **14. Dashboard** — matches `02_3.webp`

## Ship
- [ ] **15. Polish, cost guards, deploy** — rate limits, demo seeding, deploy to Vercel + Fly.io + Neon

---

**Currently:** finished step 7.
