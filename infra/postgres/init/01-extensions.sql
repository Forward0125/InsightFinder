-- ─────────────────────────────────────────────────────────────────
-- InsightFinder — Postgres extension bootstrap.
--
-- The pgvector docker image runs every .sql file in
-- /docker-entrypoint-initdb.d/ on first container init.
-- For Neon (or any other managed Postgres), run this file once
-- after creating the database:  psql "$DATABASE_URL" -f 01-extensions.sql
-- ─────────────────────────────────────────────────────────────────

-- Dense vector retrieval.
CREATE EXTENSION IF NOT EXISTS vector;

-- Trigram fuzzy-match — used later for query suggestions and
-- improving FTS recall on partial words. Postgres FTS itself is
-- built-in and does not require an extension.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Sanity check — fail loudly if either extension is missing.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    RAISE EXCEPTION 'pgvector extension failed to install';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    RAISE EXCEPTION 'pg_trgm extension failed to install';
  END IF;
END $$;
