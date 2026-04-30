'use client'

import { CheckCircle2, AlertCircle, MinusCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TopQuery } from '@/lib/api'


interface TopQueriesTableProps {
  rows: TopQuery[]
}

export function TopQueriesTable({ rows }: TopQueriesTableProps) {
  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6 flex items-center gap-2">
        <h3 className="text-sm font-medium text-foreground">
          Top Search Queries &amp; Metrics
        </h3>
        <span className="text-[11px] text-foreground-3">
          {rows.length} most recent
        </span>
      </header>

      {rows.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-foreground-3">
          No queries yet. Try one from the Query page.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-high/40">
              <tr className="text-left text-[10px] font-mono text-foreground-3 tracking-[0.1em] uppercase">
                <th className="px-4 py-2.5 w-[3.5rem]">#</th>
                <th className="px-3 py-2.5">Query</th>
                <th className="px-3 py-2.5 w-[6rem]">Mode</th>
                <th className="px-3 py-2.5 w-[5rem]">Latency</th>
                <th className="px-3 py-2.5 w-[5rem]">Cited</th>
                <th className="px-3 py-2.5 w-[5rem]">Cost</th>
                <th className="px-3 py-2.5 w-[5rem]">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((q) => (
                <tr key={q.id} className="border-t border-border/6">
                  <td className="px-4 py-2.5 font-mono text-[11px] text-foreground-3">
                    #{q.id}
                  </td>
                  <td className="px-3 py-2.5 text-[13px] text-foreground">
                    <p className="line-clamp-1 max-w-[28rem]">{q.query_text}</p>
                  </td>
                  <td className="px-3 py-2.5 text-[11px] font-mono text-foreground-2">
                    {q.retrieval_mode}
                  </td>
                  <td className="px-3 py-2.5 text-[11px] font-mono tabular-nums text-foreground-2">
                    {q.latency_total_ms ? `${q.latency_total_ms}ms` : '—'}
                  </td>
                  <td className="px-3 py-2.5 text-[11px] font-mono tabular-nums text-foreground-2">
                    {q.cited_count}/{q.results_count}
                  </td>
                  <td className="px-3 py-2.5 text-[11px] font-mono tabular-nums text-foreground-2">
                    {q.cost_usd != null ? `$${q.cost_usd.toFixed(4)}` : '—'}
                  </td>
                  <td className="px-3 py-2.5">
                    <Status passed={q.gates_passed} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}


function Status({ passed }: { passed: boolean | null }) {
  if (passed === true) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-[0.12em] text-emerald-400 bg-emerald-500/10">
        <CheckCircle2 size={10} /> pass
      </span>
    )
  }
  if (passed === false) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-[0.12em] text-amber-400 bg-amber-500/10">
        <AlertCircle size={10} /> fail
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-[0.12em] text-foreground-3 bg-surface-high">
      <MinusCircle size={10} /> n/a
    </span>
  )
}
