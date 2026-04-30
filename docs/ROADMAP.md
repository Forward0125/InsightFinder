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
- [x] **8. Async pipeline + SSE progress** — pipeline_runs/_steps tables wired; in-memory event broker; POST /pipelines/runs, GET .../events; bulk-ingested all 32 filings → 4,411 chunks / 1.64M tokens / $0.033

## Retrieval & Answer
- [x] **9. Hybrid retrieval + local rerank** — POST /search with 4 modes (bm25 / dense / hybrid / hybrid_rerank). Postgres FTS + pgvector run in parallel via two pool acquires + asyncio.gather, fused with RRF. Cross-encoder MiniLM-L6 reranks. Steady-state: hybrid ~700 ms, hybrid_rerank ~16 s on CPU
- [x] **10. Streaming answer with citations** — POST /search/answer SSE; OpenAI gpt-4o-mini generates with strict "cite [N]" prompt; citation regex extracts cited sources; queries + query_results rows persisted (~$0.0005/query, ~5s total)
- [x] **11. Eval gates** — single LLM-as-judge call (gpt-4o-mini, strict JSON schema response) scores faithfulness/relevance/hallucination after the answer streams; emitted as final SSE `eval` event; persisted to eval_scores; thresholds 0.7/0.7/0.3 (~$0.0005/eval, ~5s)

## Frontend (3 surfaces)
- [x] **12. Query Detail View** — search bar w/ mode chips, streaming answer with clickable citation chips, sources table with per-stage scores, eval gates card (animated bars + reasoning), right rail (filters/history/logs). Verified end-to-end SSE through the Next.js /api/* rewrite
- [x] **13. Pipelines View** — React Flow DAG with live SSE-driven step animation, status sidebar (All/Running/Success/Failed), filing picker modal (5 runs/IP/hr), Recent Jobs table joining chunks → docs for file labels. Visitor-triggered run goes through end-to-end DB+UI
- [x] **14. Dashboard** — `GET /dashboard/summary` rolls up KPIs / 7-day timeseries (p50/p95/queries) / top 10 queries / alerts in one round-trip; alerts are auto-emitted on eval-gate failures + pipeline failures; frontend polls every 5s and renders Recharts performance trends

## Ship
- [ ] **15. Polish, cost guards, deploy** — rate limits, demo seeding, deploy to Vercel + Fly.io + Neon

---

**Currently:** finished step 14.
