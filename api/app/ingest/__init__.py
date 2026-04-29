"""Document ingestion pipeline.

Modules:
    extract  — HTML to clean text
    chunk    — text to ~500-token chunks (paragraph-aware, with overlap)
    embed    — chunks to OpenAI embeddings (batched)
    index    — chunks + embeddings to Postgres rows
    pipeline — orchestrator: ingest_file(path) runs all four
"""
