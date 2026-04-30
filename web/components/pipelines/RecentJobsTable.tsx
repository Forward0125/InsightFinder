'use client'

import { CheckCircle2, Loader2, AlertCircle, CircleDashed } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { RunListItem } from '@/lib/api'


interface RecentJobsTableProps {
  rows:        RunListItem[]
  onSelect?:   (runId: number) => void
  selectedId?: number | null
}

export function RecentJobsTable({
  rows,
  onSelect,
  selectedId,
}: RecentJobsTableProps) {
  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2.5">
        <h3 className="text-sm font-medium text-foreground">Recent Jobs</h3>
        <span className="text-[11px] text-foreground-3">
          {rows.length} run{rows.length === 1 ? '' : 's'}
        </span>
      </header>

      {rows.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-foreground-3">
          No runs yet. Click "New Pipeline Run" to start one.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-high/40">
              <tr className="text-left text-[10px] font-mono text-foreground-3 tracking-[0.1em] uppercase">
                <th className="px-4 py-2.5 w-[3.5rem]">Run</th>
                <th className="px-3 py-2.5">Filing</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5">Trigger</th>
                <th className="px-3 py-2.5">Duration</th>
                <th className="px-3 py-2.5">Chunks</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const selected = selectedId === r.id
                return (
                  <tr
                    key={r.id}
                    onClick={onSelect ? () => onSelect(r.id) : undefined}
                    className={cn(
                      'border-t border-border/6 transition-colors',
                      onSelect && 'cursor-pointer hover:bg-surface-high',
                      selected && 'bg-accent-warm/[0.06]',
                    )}
                  >
                    <td className="px-4 py-2.5 font-mono text-[11px] text-foreground-3">
                      #{r.id}
                    </td>
                    <td className="px-3 py-2.5 text-[13px] text-foreground">
                      {r.file_label || <span className="text-foreground-3">—</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-3 py-2.5 text-[12px] text-foreground-3 font-mono">
                      {r.triggered_by || '—'}
                    </td>
                    <td className="px-3 py-2.5 text-[12px] text-foreground-2 tabular-nums">
                      {fmtDuration(r.duration_ms)}
                    </td>
                    <td className="px-3 py-2.5 text-[12px] text-foreground-2 tabular-nums">
                      {r.total_chunks > 0 ? r.total_chunks.toLocaleString() : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}


function StatusBadge({ status }: { status: RunListItem['status'] }) {
  const Icon =
    status === 'success'  ? CheckCircle2
    : status === 'running' ? Loader2
    : status === 'failed'  ? AlertCircle
    : status === 'cancelled' ? AlertCircle
    : CircleDashed

  const styles =
    status === 'success'   ? 'text-emerald-400 bg-emerald-500/10'
    : status === 'running'   ? 'text-accent-warm bg-accent-warm/10'
    : status === 'failed'    ? 'text-amber-400 bg-amber-500/10'
    : status === 'cancelled' ? 'text-foreground-3 bg-surface-high'
    : 'text-foreground-3 bg-surface-high'

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px]',
      'font-mono tracking-[0.12em] uppercase',
      styles,
    )}>
      <Icon size={11} className={status === 'running' ? 'animate-spin' : ''} />
      {status}
    </span>
  )
}


function fmtDuration(ms: number | null): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60_000)
  const s = Math.floor((ms % 60_000) / 1000)
  return `${m}m ${s}s`
}
