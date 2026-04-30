"""Dashboard summary endpoint.

Single ``GET /dashboard/summary`` rolls up everything the dashboard
needs in one round-trip:

  - KPI aggregates (avg response time, avg citations/query, eval pass
    rate, active runs)
  - 7-day timeseries (queries per day, p50/p95 latency)
  - Top 10 most-recent queries with status
  - Recent alerts feed

The frontend polls this every ~5 s -- there's no per-event semantics
so SSE would be overkill.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app import db


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ─── Schemas ─────────────────────────────────────────────────────


class KPIs(BaseModel):
    avg_response_ms:    int   | None = None
    avg_citations:      float | None = None
    eval_pass_rate:     float | None = None        # 0.0 .. 1.0
    active_runs:        int
    queries_total:      int                        # all-time
    queries_last_7d:    int


class TimeseriesPoint(BaseModel):
    day:        str            # ISO date 'YYYY-MM-DD'
    queries:    int
    p50_ms:     int | None = None
    p95_ms:     int | None = None


class TopQuery(BaseModel):
    id:               int
    query_text:       str
    retrieval_mode:   str
    latency_total_ms: int   | None = None
    cost_usd:         float | None = None
    cited_count:      int
    results_count:    int
    gates_passed:     bool  | None = None
    created_at:       Any   | None = None


class AlertRow(BaseModel):
    id:         int
    severity:   str           # info / warning / error
    title:      str
    body:       str | None = None
    source:     str | None = None
    created_at: Any  | None = None


class DashboardSummary(BaseModel):
    kpis:        KPIs
    timeseries:  list[TimeseriesPoint]
    top_queries: list[TopQuery]
    alerts:      list[AlertRow]


# ─── Endpoint ────────────────────────────────────────────────────


@router.get("/summary", response_model=DashboardSummary)
async def get_summary() -> DashboardSummary:
    async with db.get_conn() as conn:
        # KPIs ──────────────────────────────────────────────────
        kpi_row = await conn.fetchrow(
            """
            WITH last_7d AS (
                SELECT id, latency_total_ms
                FROM queries
                WHERE created_at > NOW() - INTERVAL '7 days'
            ),
            cited AS (
                SELECT query_id, count(*) AS n
                FROM query_results
                WHERE was_cited
                GROUP BY query_id
            )
            SELECT
                (SELECT avg(latency_total_ms) FROM last_7d)::int        AS avg_response_ms,
                (SELECT avg(coalesce(cited.n, 0))
                   FROM last_7d q LEFT JOIN cited ON cited.query_id = q.id) AS avg_citations,
                (SELECT count(*) FILTER (WHERE gates_passed)::float
                        / NULLIF(count(*), 0)
                   FROM eval_scores)                                     AS eval_pass_rate,
                (SELECT count(*) FROM pipeline_runs
                   WHERE status = 'running')::int                        AS active_runs,
                (SELECT count(*) FROM queries)::int                      AS queries_total,
                (SELECT count(*) FROM last_7d)::int                      AS queries_last_7d
            """,
        )
        kpis = KPIs(
            avg_response_ms = kpi_row["avg_response_ms"],
            avg_citations   = (
                float(kpi_row["avg_citations"]) if kpi_row["avg_citations"] is not None else None
            ),
            eval_pass_rate  = (
                float(kpi_row["eval_pass_rate"]) if kpi_row["eval_pass_rate"] is not None else None
            ),
            active_runs     = kpi_row["active_runs"] or 0,
            queries_total   = kpi_row["queries_total"] or 0,
            queries_last_7d = kpi_row["queries_last_7d"] or 0,
        )

        # Timeseries ────────────────────────────────────────────
        # Generate one row per day for the last 7 days even if no
        # queries that day, so the chart x-axis stays continuous.
        ts_rows = await conn.fetch(
            """
            WITH days AS (
                SELECT generate_series(
                    date_trunc('day', NOW()) - INTERVAL '6 days',
                    date_trunc('day', NOW()),
                    INTERVAL '1 day'
                )::date AS day
            )
            SELECT
                d.day::text AS day,
                count(q.id)::int AS queries,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY q.latency_total_ms)::int AS p50_ms,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY q.latency_total_ms)::int AS p95_ms
            FROM days d
            LEFT JOIN queries q
                ON date_trunc('day', q.created_at)::date = d.day
            GROUP BY d.day
            ORDER BY d.day
            """,
        )
        timeseries = [
            TimeseriesPoint(
                day=r["day"],
                queries=r["queries"],
                p50_ms=r["p50_ms"],
                p95_ms=r["p95_ms"],
            )
            for r in ts_rows
        ]

        # Top recent queries ────────────────────────────────────
        top_rows = await conn.fetch(
            """
            SELECT
                q.id, q.query_text, q.retrieval_mode,
                q.latency_total_ms, q.cost_usd, q.created_at,
                e.gates_passed,
                (SELECT count(*) FROM query_results WHERE query_id = q.id) AS results_count,
                (SELECT count(*) FROM query_results WHERE query_id = q.id AND was_cited) AS cited_count
            FROM queries q
            LEFT JOIN eval_scores e ON e.query_id = q.id
            ORDER BY q.created_at DESC
            LIMIT 10
            """,
        )
        top_queries = [
            TopQuery(
                id=r["id"],
                query_text=r["query_text"],
                retrieval_mode=r["retrieval_mode"],
                latency_total_ms=r["latency_total_ms"],
                cost_usd=float(r["cost_usd"]) if r["cost_usd"] is not None else None,
                cited_count=r["cited_count"] or 0,
                results_count=r["results_count"] or 0,
                gates_passed=r["gates_passed"],
                created_at=r["created_at"],
            )
            for r in top_rows
        ]

        # Alerts feed ───────────────────────────────────────────
        alert_rows = await conn.fetch(
            """
            SELECT id, severity::text AS severity,
                   title, body, source, created_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT 10
            """,
        )
        alerts = [AlertRow(**dict(r)) for r in alert_rows]

    return DashboardSummary(
        kpis=kpis,
        timeseries=timeseries,
        top_queries=top_queries,
        alerts=alerts,
    )
