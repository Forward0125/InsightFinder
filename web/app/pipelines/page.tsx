'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Plus, Workflow, RefreshCw } from 'lucide-react'
import {
  api,
  ApiError,
  type FilingChip,
  type PipelineInfo,
  type RunInfo,
  type RunListItem,
  type StepInfo,
  type StepName,
} from '@/lib/api'
import { cn } from '@/lib/utils'
import { PipelineDAG } from '@/components/pipelines/PipelineDAG'
import { RecentJobsTable } from '@/components/pipelines/RecentJobsTable'
import { FilingPicker } from '@/components/pipelines/FilingPicker'


/* ─── State helpers ────────────────────────────────────────── */

type StepMap = Partial<Record<StepName, StepInfo>>

const EMPTY_STEPS: StepMap = {}

interface ActiveRun {
  id:        number
  status:    RunInfo['status']
  steps:     StepMap
  meta:      RunInfo | null
  filing:    FilingChip | null
  startedAt: number
}


/* ─── Page ──────────────────────────────────────────────────── */

export default function PipelinesPage() {
  const [pipelines, setPipelines] = useState<PipelineInfo[] | null>(null)
  const [runs,      setRuns]      = useState<RunListItem[]>([])
  const [active,    setActive]    = useState<ActiveRun | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pickerErr, setPickerErr] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<RunListItem['status'] | 'all'>('all')

  const abortRef = useRef<AbortController | null>(null)

  const pipelineId = pipelines?.[0]?.id ?? null

  /* ─── Initial load ─────────────────────────────────────────── */

  useEffect(() => {
    api.listPipelines().then(setPipelines).catch(() => setPipelines([]))
  }, [])

  const refreshRuns = useCallback(async () => {
    if (pipelineId == null) return
    try {
      const list = await api.listRuns(pipelineId, { limit: 30 })
      setRuns(list)
    } catch {
      /* swallow -- shown via toasts later */
    }
  }, [pipelineId])

  useEffect(() => { refreshRuns() }, [refreshRuns])

  // Light polling so finished runs show up even without an active subscription.
  useEffect(() => {
    if (pipelineId == null) return
    const id = window.setInterval(refreshRuns, 8000)
    return () => window.clearInterval(id)
  }, [pipelineId, refreshRuns])

  // Cancel any open SSE on unmount.
  useEffect(() => () => abortRef.current?.abort(), [])

  /* ─── Subscribe to a run's SSE stream ──────────────────────── */

  const subscribe = useCallback(
    async (runId: number, filing: FilingChip | null = null) => {
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac

      // Seed with the snapshot first.
      let snapshot: RunInfo | null = null
      try {
        snapshot = await api.getRun(runId)
      } catch {
        snapshot = null
      }

      const seedSteps: StepMap = {}
      if (snapshot) {
        for (const s of snapshot.steps) seedSteps[s.name] = s
      }

      setActive({
        id:        runId,
        status:    snapshot?.status ?? 'queued',
        steps:     seedSteps,
        meta:      snapshot,
        filing,
        startedAt: Date.now(),
      })

      try {
        for await (const ev of api.streamRunEvents(runId, { signal: ac.signal })) {
          if (ac.signal.aborted) return
          setActive((curr) => {
            if (!curr || curr.id !== runId) return curr
            return reduceRunEvent(curr, ev)
          })

          if (ev.type === 'run.completed' || ev.type === 'run.failed' || ev.type === 'stream.end') {
            // Refresh the recent-jobs table once the run is done.
            void refreshRuns()
            if (ev.type === 'stream.end') return
          }
        }
      } catch (err) {
        if (ac.signal.aborted) return
        // eslint-disable-next-line no-console
        console.error('run stream failed', err)
      }
    },
    [refreshRuns],
  )

  /* ─── Picker → start a run ────────────────────────────────── */

  const handlePick = useCallback(
    async (filing: FilingChip) => {
      setPickerErr(null)
      try {
        const { run_id } = await api.createRun(filing.local_path)
        setPickerOpen(false)
        await subscribe(run_id, filing)
        await refreshRuns()
      } catch (err) {
        if (err instanceof ApiError && err.status === 429) {
          setPickerErr('Rate limit hit (5 runs / hour / IP). Try again later.')
        } else {
          setPickerErr(err instanceof Error ? err.message : 'failed to start run')
        }
      }
    },
    [subscribe, refreshRuns],
  )

  /* ─── Filtered jobs list ──────────────────────────────────── */

  const visibleRuns = useMemo(() => {
    if (statusFilter === 'all') return runs
    return runs.filter((r) => r.status === statusFilter)
  }, [runs, statusFilter])

  /* ─── Render ──────────────────────────────────────────────── */

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[200px_1fr] gap-6 px-6 py-8 md:py-10">
      {/* Sidebar (filters) */}
      <aside className="space-y-3">
        <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase">
          Pipeline Runs
        </p>
        {(['all', 'running', 'success', 'failed'] as const).map((s) => {
          const count =
            s === 'all' ? runs.length :
            runs.filter((r) => r.status === s).length
          const active = statusFilter === s
          return (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                'w-full flex items-center justify-between px-3 py-2 rounded-lg text-[13px]',
                'transition-colors',
                active
                  ? 'bg-surface-high text-foreground'
                  : 'text-foreground-2 hover:bg-surface-high/50 hover:text-foreground',
              )}
            >
              <span className="capitalize">{s}</span>
              <span className="text-[10px] font-mono text-foreground-3">{count}</span>
            </button>
          )
        })}
      </aside>

      {/* Main column */}
      <div className="min-w-0 space-y-6">
        <header className="flex items-end justify-between gap-3 flex-wrap">
          <div>
            <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-2">
              Pipelines
            </p>
            <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight">
              Pipeline Operations
            </h1>
            <p className="mt-2 text-[14px] text-foreground-2 max-w-xl">
              Document ingestion as a DAG. Trigger a fresh run on any filing
              and watch the steps animate in real time.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refreshRuns()}
              className="p-2 rounded-lg text-foreground-3 hover:text-foreground hover:bg-surface-high"
              title="Refresh"
            >
              <RefreshCw size={15} />
            </button>
            <button
              onClick={() => { setPickerErr(null); setPickerOpen(true) }}
              className={cn(
                'inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-[13px] font-medium',
                'bg-accent-warm text-white hover:bg-accent-violet transition-colors',
              )}
            >
              <Plus size={14} />
              New Pipeline Run
            </button>
          </div>
        </header>

        {/* Active run card */}
        <section className={cn(
          'rounded-xl border overflow-hidden',
          active ? 'bg-surface border-accent-warm/20' : 'bg-surface border-border/8',
        )}>
          <div className="px-5 py-3 border-b border-border/6 flex items-center gap-3">
            <Workflow size={15} className="text-accent-warm" />
            <h3 className="text-sm font-medium text-foreground">
              {active ? `Run #${active.id}` : 'No active run'}
            </h3>
            {active?.filing && (
              <span className="text-[12px] text-foreground-2">
                {active.filing.ticker} <span className="text-foreground-3">·</span> {active.filing.filing_type}
                <span className="text-foreground-3"> · period </span>
                {active.filing.period_of_report}
              </span>
            )}
            <div className="flex-1" />
            {active && (
              <span className={cn(
                'text-[10px] font-mono px-2 py-0.5 rounded uppercase tracking-[0.15em]',
                active.status === 'success'  && 'text-emerald-400 bg-emerald-500/10',
                active.status === 'running'  && 'text-accent-warm bg-accent-warm/10',
                active.status === 'failed'   && 'text-amber-400 bg-amber-500/10',
                active.status === 'queued'   && 'text-foreground-3 bg-surface-high',
              )}>
                {active.status}
              </span>
            )}
          </div>
          <div className="p-4">
            <PipelineDAG
              steps={active?.steps ?? EMPTY_STEPS}
              runStatus={active?.status ?? 'idle'}
            />
            {!active && (
              <p className="mt-4 text-center text-[13px] text-foreground-3">
                Click "New Pipeline Run" or pick a row from Recent Jobs to attach.
              </p>
            )}
            {active?.meta && (
              <ActiveStats run={active} />
            )}
          </div>
        </section>

        {/* Recent jobs */}
        <RecentJobsTable
          rows={visibleRuns}
          selectedId={active?.id ?? null}
          onSelect={(runId) => subscribe(runId, null)}
        />
      </div>

      {/* Picker modal */}
      <FilingPicker
        isOpen={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={handlePick}
        errorText={pickerErr}
      />
    </div>
  )
}


/* ─── Reducer for incoming SSE events ──────────────────────── */

import type { RunEvent } from '@/lib/api'

function reduceRunEvent(curr: ActiveRun, ev: RunEvent): ActiveRun {
  switch (ev.type) {
    case 'snapshot': {
      const steps: StepMap = {}
      for (const s of ev.run.steps) steps[s.name] = s
      return { ...curr, steps, status: ev.run.status, meta: ev.run }
    }
    case 'run.started':
      return { ...curr, status: 'running' }
    case 'step.started': {
      const prev = curr.steps[ev.step]
      return {
        ...curr,
        steps: {
          ...curr.steps,
          [ev.step]: {
            ...(prev ?? {
              name: ev.step,
              progress_pct: 0,
              started_at: null,
              finished_at: null,
              metadata: null,
            }),
            status: 'running',
            progress_pct: 0,
          } as StepInfo,
        },
      }
    }
    case 'step.progress': {
      const prev = curr.steps[ev.step]
      if (!prev) return curr
      return {
        ...curr,
        steps: {
          ...curr.steps,
          [ev.step]: { ...prev, progress_pct: ev.progress_pct },
        },
      }
    }
    case 'step.completed': {
      const { type, step, ...rest } = ev as Record<string, unknown> & { step: StepName }
      const prev = curr.steps[step]
      return {
        ...curr,
        steps: {
          ...curr.steps,
          [step]: {
            ...(prev ?? {
              name: step,
              started_at: null,
              finished_at: null,
            }),
            status: 'success',
            progress_pct: 100,
            metadata: rest as Record<string, unknown>,
          } as StepInfo,
        },
      }
    }
    case 'run.completed':
      return { ...curr, status: 'success' }
    case 'run.failed':
      return { ...curr, status: 'failed' }
    case 'stream.end':
      return curr
  }
  return curr
}


/* ─── Footer stats under the DAG ────────────────────────────── */

function ActiveStats({ run }: { run: ActiveRun }) {
  const totalChunks = Object.values(run.steps)
    .map((s) => (s?.metadata as { chunks?: number } | null)?.chunks)
    .find((n): n is number => typeof n === 'number')

  const totalTokens = (run.steps.chunk?.metadata as { tokens?: number } | null)?.tokens
  const cost = (run.steps.embed?.metadata as { cost_usd?: number } | null)?.cost_usd
  const elapsed = Math.round((Date.now() - run.startedAt) / 1000)

  return (
    <div className="mt-4 pt-4 border-t border-border/6 flex flex-wrap gap-x-6 gap-y-1 text-[11px] font-mono text-foreground-3">
      <span>elapsed {elapsed}s</span>
      {totalChunks != null && <span>chunks {totalChunks}</span>}
      {totalTokens != null && <span>tokens {totalTokens.toLocaleString()}</span>}
      {cost != null && <span>cost ${cost.toFixed(4)}</span>}
    </div>
  )
}
