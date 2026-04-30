/**
 * Typed client for the InsightFinder FastAPI backend.
 *
 * In dev, requests go to /api/* which Next.js rewrites to the API host
 * (see next.config.ts). In prod, they hit NEXT_PUBLIC_API_URL directly.
 */

const API_BASE = '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
  })

  if (!res.ok) {
    let body: unknown
    try { body = await res.json() } catch { /* response was not JSON */ }
    throw new ApiError(`${res.status} ${res.statusText}`, res.status, body)
  }

  return res.json() as Promise<T>
}

// ─── Health ──────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok'
  db: 'ok' | 'unreachable'
}

// ─── Pipelines ───────────────────────────────────────────────────

export type PipelineStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled'
export type StepName = 'extract' | 'chunk' | 'embed' | 'index'

export interface PipelineInfo {
  id:           number
  slug:         string
  name:         string
  description:  string | null
  is_demo:      boolean
  runs_total:   number
  runs_running: number
  runs_success: number
  runs_failed:  number
}

export interface FilingChip {
  ticker:           string
  filing_type:      string
  period_of_report: string
  accession_number: string
  local_path:       string
  size_bytes:       number
}

export interface RunListItem {
  id:           number
  status:       PipelineStatus
  triggered_by: string | null
  started_at:   string | null
  finished_at:  string | null
  total_chunks: number
  duration_ms:  number | null
  file_label:   string | null
}

export interface StepInfo {
  name:         StepName
  status:       PipelineStatus
  progress_pct: number
  started_at:   string | null
  finished_at:  string | null
  metadata:     Record<string, unknown> | null
}

export interface RunInfo {
  id:            number
  pipeline_id:   number
  status:        PipelineStatus
  triggered_by:  string | null
  started_at:    string | null
  finished_at:   string | null
  total_files:   number
  total_pages:   number
  total_chunks:  number
  error_message: string | null
  steps:         StepInfo[]
}

export interface CreateRunResponse {
  run_id: number
}

// ─── Pipeline run SSE events ─────────────────────────────────────

export interface RunSnapshotEvent {
  type: 'snapshot'
  run:  RunInfo
}

export interface RunStartedEvent {
  type:        'run.started'
  run_id:      number
  ticker?:     string
  filing_type?: string
  period?:     string
  local_path?: string
}

export interface StepStartedEvent {
  type:   'step.started'
  step:   StepName
}

export interface StepProgressEvent {
  type:         'step.progress'
  step:         StepName
  progress_pct: number
  batch?:       number
  batches?:     number
}

export interface StepCompletedEvent {
  type:    'step.completed'
  step:    StepName
  [key: string]: unknown
}

export interface RunCompletedEvent {
  type:        'run.completed'
  run_id:      number
  document_id: number
  chunks:      number
  tokens:      number
  seconds:     number
  cost_usd:    number
}

export interface RunFailedEvent {
  type:   'run.failed'
  run_id: number
  error:  string
}

export interface StreamEndEvent {
  type: 'stream.end'
}

export type RunEvent =
  | RunSnapshotEvent
  | RunStartedEvent
  | StepStartedEvent
  | StepProgressEvent
  | StepCompletedEvent
  | RunCompletedEvent
  | RunFailedEvent
  | StreamEndEvent

// ─── Dashboard ───────────────────────────────────────────────────

export interface KPIs {
  avg_response_ms: number | null
  avg_citations:   number | null
  eval_pass_rate:  number | null
  active_runs:     number
  queries_total:   number
  queries_last_7d: number
}

export interface TimeseriesPoint {
  day:     string
  queries: number
  p50_ms:  number | null
  p95_ms:  number | null
}

export interface TopQuery {
  id:               number
  query_text:       string
  retrieval_mode:   string
  latency_total_ms: number | null
  cost_usd:         number | null
  cited_count:      number
  results_count:    number
  gates_passed:     boolean | null
  created_at:       string  | null
}

export type AlertSeverity = 'info' | 'warning' | 'error'

export interface AlertRow {
  id:         number
  severity:   AlertSeverity
  title:      string
  body:       string | null
  source:     string | null
  created_at: string | null
}

export interface DashboardSummary {
  kpis:        KPIs
  timeseries:  TimeseriesPoint[]
  top_queries: TopQuery[]
  alerts:      AlertRow[]
}

// ─── Search / Answer types ───────────────────────────────────────

export type SearchMode = 'bm25' | 'dense' | 'hybrid' | 'hybrid_rerank'

export interface SearchSource {
  rank: number
  chunk_id: number
  ticker: string
  filing_type: string
  period_of_report: string
  accession_number: string
  chunk_index: number
  text: string
  bm25_score:   number | null
  dense_score:  number | null
  fused_score:  number | null
  rerank_score: number | null
}

export interface MetaEvent {
  type: 'meta'
  model: string
  mode:  SearchMode
  sources: SearchSource[]
  search_latency_ms: Record<string, number>
}

export interface TokenEvent {
  type: 'token'
  text: string
}

export interface DoneEvent {
  type: 'done'
  query_id:      number | null
  cited:         number[]
  response_text: string
  tokens_in:     number
  tokens_out:    number
  cost_usd:      number
  latency_ms:    Record<string, number>
  message?:      string
}

export interface EvalEvent {
  type: 'eval'
  query_id:           number
  faithfulness:       number
  answer_relevance:   number
  hallucination_risk: number
  gates_passed:       boolean
  reasoning:          string
  evaluator_model:    string
  tokens_in:          number
  tokens_out:         number
  cost_usd:           number
  latency_ms:         number
}

export interface ErrorEvent {
  type: 'error' | 'eval_failed'
  error: string
}

export type AnswerEvent =
  | MetaEvent
  | TokenEvent
  | DoneEvent
  | EvalEvent
  | ErrorEvent

export interface AnswerRequest {
  query:        string
  mode?:        SearchMode
  top_k?:       number
  candidates?:  number
}

// ─── Endpoints ───────────────────────────────────────────────────

export const api = {
  health: () => request<HealthResponse>('/health'),

  // ─── Pipelines ────────────────────────────────────────────────
  listPipelines: () => request<PipelineInfo[]>('/pipelines'),

  listFilings: () => request<FilingChip[]>('/pipelines/filings'),

  listRuns: (pipelineId: number, opts: { status?: PipelineStatus; limit?: number } = {}) => {
    const qs = new URLSearchParams()
    if (opts.status) qs.set('status', opts.status)
    if (opts.limit)  qs.set('limit', String(opts.limit))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<RunListItem[]>(`/pipelines/${pipelineId}/runs${suffix}`)
  },

  getRun: (runId: number) => request<RunInfo>(`/pipelines/runs/${runId}`),

  // ─── Dashboard ────────────────────────────────────────────────
  dashboardSummary: () => request<DashboardSummary>('/dashboard/summary'),

  createRun: (localPath: string) =>
    request<CreateRunResponse>('/pipelines/runs', {
      method: 'POST',
      body: JSON.stringify({ local_path: localPath }),
    }),

  /** SSE stream of live run progress. Async-iterable of events. */
  async *streamRunEvents(
    runId: number,
    opts: { signal?: AbortSignal } = {},
  ): AsyncGenerator<RunEvent, void, unknown> {
    const res = await fetch(`${API_BASE}/pipelines/runs/${runId}/events`, {
      signal: opts.signal,
    })
    if (!res.ok || !res.body) {
      throw new ApiError(`${res.status} ${res.statusText}`, res.status)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''

        for (const raw of events) {
          if (!raw.trim() || raw.startsWith(':')) continue
          let data = ''
          for (const line of raw.split('\n')) {
            if (line.startsWith('data: ')) data += line.slice(6)
          }
          if (!data) continue
          try {
            yield JSON.parse(data) as RunEvent
          } catch {
            /* malformed event */
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },

  /** Open an SSE stream for a RAG answer. Async-iterable of events. */
  async *streamAnswer(
    req: AnswerRequest,
    opts: { signal?: AbortSignal } = {},
  ): AsyncGenerator<AnswerEvent, void, unknown> {
    const res = await fetch(`${API_BASE}/search/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal: opts.signal,
    })
    if (!res.ok || !res.body) {
      throw new ApiError(`${res.status} ${res.statusText}`, res.status)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE events are terminated by a blank line (\n\n).
        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''

        for (const raw of events) {
          if (!raw.trim()) continue
          let data = ''
          for (const line of raw.split('\n')) {
            if (line.startsWith('data: ')) data += line.slice(6)
          }
          if (!data) continue
          try {
            yield JSON.parse(data) as AnswerEvent
          } catch {
            /* malformed event; skip */
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
}
