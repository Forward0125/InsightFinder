'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  api,
  ApiError,
  type AnswerEvent,
  type DoneEvent,
  type EvalEvent,
  type MetaEvent,
  type SearchMode,
  type SearchSource,
} from '@/lib/api'
import { QueryInput } from '@/components/query/QueryInput'
import { AnswerCard } from '@/components/query/AnswerCard'
import { SourcesTable } from '@/components/query/SourcesTable'
import { EvalGatesCard } from '@/components/query/EvalGatesCard'
import { ActiveFilters } from '@/components/right-rail/ActiveFilters'
import {
  QueryHistory,
  pushHistory,
} from '@/components/right-rail/QueryHistory'
import {
  SystemLogs,
  type LogLine,
} from '@/components/right-rail/SystemLogs'


/* ─── Page state ────────────────────────────────────────────── */

type Status = 'idle' | 'streaming' | 'completed' | 'error'

interface PageState {
  status:      Status
  query:       string
  mode:        SearchMode
  meta:        MetaEvent | null
  answer:      string
  cited:       Set<number>
  done:        DoneEvent | null
  evaluation:  EvalEvent | null
  errorText:   string | null
}

const INITIAL_STATE: PageState = {
  status:     'idle',
  query:      '',
  mode:       'hybrid',
  meta:       null,
  answer:     '',
  cited:      new Set(),
  done:       null,
  evaluation: null,
  errorText:  null,
}


/* ─── Page ──────────────────────────────────────────────────── */

export default function QueryPage() {
  const [state,    setState]    = useState<PageState>(INITIAL_STATE)
  const [logs,     setLogs]     = useState<LogLine[]>([])
  const [history,  setHistory]  = useState(0)
  const [hovered,  setHovered]  = useState<number | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  // Cancel any in-flight stream when the component unmounts.
  useEffect(() => () => abortRef.current?.abort(), [])

  const log = useCallback((level: LogLine['level'], text: string) => {
    setLogs((prev) => [...prev, { ts: Date.now(), level, text }].slice(-200))
  }, [])

  const onSubmit = useCallback(
    async (query: string, mode: SearchMode) => {
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac

      setState({
        status:     'streaming',
        query,
        mode,
        meta:       null,
        answer:     '',
        cited:      new Set(),
        done:       null,
        evaluation: null,
        errorText:  null,
      })

      log('INFO', `Query received: "${query}"`)
      log('INFO', `Mode: ${mode}`)

      try {
        for await (const event of api.streamAnswer(
          { query, mode, top_k: 8, candidates: 30 },
          { signal: ac.signal },
        )) {
          if (ac.signal.aborted) return
          handleEvent(event, setState, log)
        }
      } catch (err) {
        if (ac.signal.aborted) return
        const msg = err instanceof ApiError
          ? `${err.status} ${err.message}`
          : err instanceof Error ? err.message : 'unknown error'
        log('ERROR', `Stream failed: ${msg}`)
        setState((s) => ({ ...s, status: 'error', errorText: msg }))
      }
    },
    [log],
  )

  // Persist to history when the run is fully done (eval received).
  useEffect(() => {
    if (state.status === 'completed' && state.done && state.evaluation) {
      pushHistory({
        query:  state.query,
        mode:   state.mode,
        ts:     Date.now(),
        cost:   (state.done.cost_usd ?? 0) + (state.evaluation.cost_usd ?? 0),
        passed: state.evaluation.gates_passed,
      })
      setHistory((v) => v + 1)
    }
  }, [state.status, state.done, state.evaluation, state.query, state.mode])

  const sources: SearchSource[] = state.meta?.sources ?? []

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-6 px-6 py-8 md:py-10">
      {/* Main column */}
      <div className="space-y-6 min-w-0">
        <header>
          <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-2">
            Query
          </p>
          <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight">
            Ask the filings.
          </h1>
          <p className="mt-2 text-[14px] text-foreground-2 max-w-2xl">
            Cited-answer search across Apple, Microsoft, Google, Amazon,
            Tesla, Nvidia, Meta, and Netflix 10-K and 10-Q reports.
          </p>
        </header>

        <QueryInput
          onSubmit={onSubmit}
          disabled={state.status === 'streaming'}
        />

        <AnswerCard
          answer={state.answer}
          cited={state.cited}
          status={state.status}
          errorText={state.errorText}
          hoveredCite={hovered}
          onCiteClick={(n) => {
            // Scroll the row into view + flash hover.
            setHovered(n)
            const el = document.querySelector<HTMLElement>(
              `tr[data-rank="${n}"]`,
            )
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
            // Drop hover after a short delay so it's visible but doesn't stick.
            window.setTimeout(() => setHovered(null), 1200)
          }}
        />

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
          <SourcesTable
            sources={sources}
            cited={state.cited}
            hoveredCite={hovered}
            onRowHover={setHovered}
            mode={state.meta?.mode}
          />
          <EvalGatesCard
            evaluation={state.evaluation}
            pending={state.status === 'streaming' || (state.done != null && state.evaluation == null && state.status === 'completed')}
          />
        </div>

        {/* Latency / cost footer */}
        {state.done && (
          <FooterStats done={state.done} evaluation={state.evaluation} />
        )}
      </div>

      {/* Right rail */}
      <aside className="space-y-4 hidden xl:block">
        <ActiveFilters />
        <QueryHistory
          version={history}
          onSelect={(q) => onSubmit(q, state.mode)}
        />
        <SystemLogs lines={logs} onClear={() => setLogs([])} />
      </aside>
    </div>
  )
}


/* ─── Event handler ─────────────────────────────────────────── */

function handleEvent(
  event: AnswerEvent,
  setState: React.Dispatch<React.SetStateAction<PageState>>,
  log: (level: LogLine['level'], text: string) => void,
) {
  switch (event.type) {
    case 'meta':
      log('INFO', `Retrieved ${event.sources.length} candidate chunks (${event.mode})`)
      log('DEBUG', `Embedding latency ${event.search_latency_ms.embed_ms ?? 0}ms · retrieve ${event.search_latency_ms.retrieve_ms ?? 0}ms`)
      setState((s) => ({ ...s, meta: event }))
      break

    case 'token':
      setState((s) => ({ ...s, answer: s.answer + event.text }))
      break

    case 'done':
      log('INFO', `Answer streamed: ${event.tokens_out} tokens, $${event.cost_usd.toFixed(4)}`)
      log('DEBUG', `Total latency ${event.latency_ms.total_ms}ms · generation ${event.latency_ms.generate_ms}ms`)
      setState((s) => ({
        ...s,
        status: 'completed',
        cited:  new Set(event.cited),
        done:   event,
      }))
      break

    case 'eval':
      log(
        event.gates_passed ? 'INFO' : 'WARN',
        `Eval gates ${event.gates_passed ? 'PASS' : 'FAIL'} — fai=${event.faithfulness.toFixed(2)} rel=${event.answer_relevance.toFixed(2)} halo=${event.hallucination_risk.toFixed(2)}`,
      )
      setState((s) => ({ ...s, evaluation: event }))
      break

    case 'error':
      log('ERROR', `Stream error: ${event.error}`)
      setState((s) => ({ ...s, status: 'error', errorText: event.error }))
      break

    case 'eval_failed':
      log('WARN', `Eval failed: ${event.error}`)
      break
  }
}


/* ─── Footer ────────────────────────────────────────────────── */

function FooterStats({
  done,
  evaluation,
}: {
  done:       DoneEvent
  evaluation: EvalEvent | null
}) {
  const totalMs    = done.latency_ms.total_ms ?? 0
  const generateMs = done.latency_ms.generate_ms ?? 0
  const totalCost  = (done.cost_usd ?? 0) + (evaluation?.cost_usd ?? 0)

  return (
    <div className="flex flex-wrap gap-x-6 gap-y-1 text-[11px] font-mono text-foreground-3 pt-2 border-t border-border/6">
      <span>total {totalMs}ms</span>
      <span>generate {generateMs}ms</span>
      {evaluation && <span>eval {evaluation.latency_ms}ms</span>}
      <span>tokens in/out {done.tokens_in}/{done.tokens_out}</span>
      <span>cost ${totalCost.toFixed(4)}</span>
      {done.query_id != null && <span>query #{done.query_id}</span>}
    </div>
  )
}
