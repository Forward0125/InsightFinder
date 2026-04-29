# InsightFinder — Build Roadmap

15 sequenced steps from empty folder to deployed product.

## Foundation
- [x] **1. Scaffold project folder** — README, .gitignore, .env.example, docker-compose.yml, folder tree
- [x] **2. Postgres + pgvector running** — Neon connection verified, `vector` + `pg_trgm` extensions installed
- [x] **3. FastAPI backend skeleton** — settings, asyncpg pool, `/health` returns `{"status":"ok","db":"ok"}`
- [x] **4. Database schema + migrations** — 10 tables, HNSW + GIN indexes, 2 enums, applied via Alembic
- [ ] **5. Next.js frontend skeleton** — Next 15 + Tailwind + design tokens copied from portfolio

## Ingestion
- [ ] **6. SEC filing fetcher** — script downloading latest 10-K + 10-Q for 8 companies
- [ ] **7. PDF → chunks pipeline (sync)** — extract → chunk → embed → index a single doc end-to-end
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

**Currently:** finished step 4.
