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
