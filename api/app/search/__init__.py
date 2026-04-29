"""Retrieval & reranking for the InsightFinder corpus.

Modules:
    retrieve  — BM25 (Postgres FTS) and dense (pgvector) ranked lists
                + reciprocal-rank fusion to combine them
    rerank    — local cross-encoder (BAAI/bge-reranker-base)
    service   — public ``search()`` orchestrator used by the HTTP layer
"""
