#!/usr/bin/env bash
# Verify that Postgres is reachable and pgvector + pg_trgm are loaded.
# Reads DATABASE_URL from the environment (or .env if loaded).
#
# Usage:
#   scripts/db/verify.sh                           # uses $DATABASE_URL
#   DATABASE_URL=postgresql://... scripts/db/verify.sh

set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set. Either:"
  echo "  - export DATABASE_URL=postgresql://..."
  echo "  - or source .env first"
  exit 1
fi

echo "→ Pinging Postgres at $DATABASE_URL"
psql "$DATABASE_URL" -c "SELECT version();" >/dev/null
echo "  ok"

echo "→ Checking extensions"
psql "$DATABASE_URL" -c "
  SELECT extname, extversion
  FROM pg_extension
  WHERE extname IN ('vector', 'pg_trgm')
  ORDER BY extname;
"

echo "→ Round-tripping a vector literal"
psql "$DATABASE_URL" -c "SELECT '[1,2,3]'::vector AS sample;"

echo
echo "Postgres + pgvector verified."
