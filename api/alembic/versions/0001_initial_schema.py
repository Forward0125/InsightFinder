"""Initial schema -- companies, documents, pipelines, chunks, queries, evals, alerts.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-29
"""

from __future__ import annotations

from alembic import op


# Alembic identifiers.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the full InsightFinder schema in one migration."""

    # ─── Extensions (idempotent; usually already enabled by infra/) ──
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # ─── Enums ───────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE pipeline_status AS ENUM (
            'queued', 'running', 'success', 'failed', 'cancelled'
        );
    """)
    op.execute("""
        CREATE TYPE alert_severity AS ENUM ('info', 'warning', 'error');
    """)

    # ─── Companies (SEC EDGAR public companies) ──────────────────────
    op.execute("""
        CREATE TABLE companies (
            id          SERIAL PRIMARY KEY,
            ticker      TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            cik         TEXT NOT NULL UNIQUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # ─── Documents (filing metadata) ─────────────────────────────────
    op.execute("""
        CREATE TABLE documents (
            id                BIGSERIAL PRIMARY KEY,
            company_id        INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            filing_type       TEXT NOT NULL,            -- '10-K' / '10-Q'
            filing_date       DATE NOT NULL,
            period_of_report  DATE NOT NULL,
            title             TEXT NOT NULL,
            source_url        TEXT NOT NULL,
            accession_number  TEXT UNIQUE,              -- SEC accession number
            raw_path          TEXT,                     -- local path to PDF
            total_pages       INTEGER,
            ingested_at       TIMESTAMPTZ,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (company_id, filing_type, period_of_report)
        );
    """)
    op.execute("CREATE INDEX idx_documents_company ON documents(company_id);")
    op.execute("CREATE INDEX idx_documents_filing_type ON documents(filing_type);")

    # ─── Pipelines (named knowledge-base configs) ────────────────────
    op.execute("""
        CREATE TABLE pipelines (
            id           SERIAL PRIMARY KEY,
            slug         TEXT NOT NULL UNIQUE,
            name         TEXT NOT NULL,
            description  TEXT,
            is_demo      BOOLEAN NOT NULL DEFAULT FALSE,
            config       JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # ─── Pipeline Runs (each ingestion job) ──────────────────────────
    op.execute("""
        CREATE TABLE pipeline_runs (
            id              BIGSERIAL PRIMARY KEY,
            pipeline_id     INTEGER NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
            status          pipeline_status NOT NULL DEFAULT 'queued',
            triggered_by    TEXT,                       -- 'cron' / 'visitor' / 'admin'
            ip_address      INET,
            started_at      TIMESTAMPTZ,
            finished_at     TIMESTAMPTZ,
            total_files     INTEGER NOT NULL DEFAULT 0,
            total_pages     INTEGER NOT NULL DEFAULT 0,
            total_chunks    INTEGER NOT NULL DEFAULT 0,
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_pipeline_runs_pipeline ON pipeline_runs(pipeline_id);")
    op.execute("CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);")
    op.execute("CREATE INDEX idx_pipeline_runs_created ON pipeline_runs(created_at DESC);")

    # ─── Pipeline Steps (DAG nodes for live viz) ─────────────────────
    op.execute("""
        CREATE TABLE pipeline_steps (
            id            BIGSERIAL PRIMARY KEY,
            run_id        BIGINT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
            name          TEXT NOT NULL,                -- 'extract'/'chunk'/'embed'/'index'/'eval_gate'
            status        pipeline_status NOT NULL DEFAULT 'queued',
            progress_pct  INTEGER NOT NULL DEFAULT 0,
            started_at    TIMESTAMPTZ,
            finished_at   TIMESTAMPTZ,
            metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
            UNIQUE (run_id, name)
        );
    """)
    op.execute("CREATE INDEX idx_pipeline_steps_run ON pipeline_steps(run_id);")

    # ─── Chunks (the searchable content) ─────────────────────────────
    # tsv is a generated column kept in sync with text. embedding is
    # 1536-dim to match OpenAI text-embedding-3-small. HNSW index for
    # ANN search; GIN index for BM25.
    op.execute("""
        CREATE TABLE chunks (
            id              BIGSERIAL PRIMARY KEY,
            document_id     BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            pipeline_run_id BIGINT REFERENCES pipeline_runs(id) ON DELETE SET NULL,
            chunk_index     INTEGER NOT NULL,
            text            TEXT NOT NULL,
            page_number     INTEGER,
            token_count     INTEGER,
            tsv             tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
            embedding       vector(1536),
            metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (document_id, chunk_index)
        );
    """)
    op.execute("CREATE INDEX idx_chunks_document ON chunks(document_id);")
    op.execute("CREATE INDEX idx_chunks_tsv ON chunks USING GIN (tsv);")
    op.execute("""
        CREATE INDEX idx_chunks_embedding
        ON chunks USING hnsw (embedding vector_cosine_ops);
    """)

    # ─── Queries (search log) ────────────────────────────────────────
    op.execute("""
        CREATE TABLE queries (
            id                    BIGSERIAL PRIMARY KEY,
            pipeline_id           INTEGER REFERENCES pipelines(id) ON DELETE SET NULL,
            query_text            TEXT NOT NULL,
            retrieval_mode        TEXT NOT NULL,           -- 'dense'/'hybrid'/'hybrid_rerank'
            response_text         TEXT,
            generator_model       TEXT,
            latency_total_ms      INTEGER,
            latency_retrieval_ms  INTEGER,
            latency_rerank_ms     INTEGER,
            latency_generation_ms INTEGER,
            tokens_in             INTEGER,
            tokens_out            INTEGER,
            cost_usd              NUMERIC(10, 6),
            ip_address            INET,
            user_agent            TEXT,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_queries_created ON queries(created_at DESC);")
    op.execute("CREATE INDEX idx_queries_pipeline ON queries(pipeline_id);")

    # ─── Query Results (which chunks were retrieved/cited per query) ─
    op.execute("""
        CREATE TABLE query_results (
            id            BIGSERIAL PRIMARY KEY,
            query_id      BIGINT NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
            chunk_id      BIGINT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            rank          INTEGER NOT NULL,
            dense_score   REAL,
            bm25_score    REAL,
            rerank_score  REAL,
            was_cited     BOOLEAN NOT NULL DEFAULT FALSE,
            UNIQUE (query_id, chunk_id)
        );
    """)
    op.execute("CREATE INDEX idx_query_results_query ON query_results(query_id);")

    # ─── Eval Scores (per-query evaluation gates) ────────────────────
    op.execute("""
        CREATE TABLE eval_scores (
            id                  BIGSERIAL PRIMARY KEY,
            query_id            BIGINT NOT NULL UNIQUE REFERENCES queries(id) ON DELETE CASCADE,
            faithfulness        REAL,                -- 0.0 - 1.0
            answer_relevance    REAL,                -- 0.0 - 1.0
            hallucination_risk  REAL,                -- 0.0 (low) - 1.0 (high)
            gates_passed        BOOLEAN,
            evaluator_model     TEXT,
            evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # ─── Alerts (system status feed for the dashboard) ───────────────
    op.execute("""
        CREATE TABLE alerts (
            id              BIGSERIAL PRIMARY KEY,
            severity        alert_severity NOT NULL,
            title           TEXT NOT NULL,
            body            TEXT,
            source          TEXT,                    -- 'ingestion'/'eval'/'system'
            metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
            acknowledged_at TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX idx_alerts_created ON alerts(created_at DESC);")
    op.execute("CREATE INDEX idx_alerts_severity ON alerts(severity);")


def downgrade() -> None:
    """Drop everything in reverse order."""
    op.execute("DROP TABLE IF EXISTS alerts CASCADE;")
    op.execute("DROP TABLE IF EXISTS eval_scores CASCADE;")
    op.execute("DROP TABLE IF EXISTS query_results CASCADE;")
    op.execute("DROP TABLE IF EXISTS queries CASCADE;")
    op.execute("DROP TABLE IF EXISTS chunks CASCADE;")
    op.execute("DROP TABLE IF EXISTS pipeline_steps CASCADE;")
    op.execute("DROP TABLE IF EXISTS pipeline_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS pipelines CASCADE;")
    op.execute("DROP TABLE IF EXISTS documents CASCADE;")
    op.execute("DROP TABLE IF EXISTS companies CASCADE;")
    op.execute("DROP TYPE IF EXISTS alert_severity;")
    op.execute("DROP TYPE IF EXISTS pipeline_status;")
    # Don't drop extensions -- they may be used by other databases.
