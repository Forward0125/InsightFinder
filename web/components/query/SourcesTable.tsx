'use client'

import { Layers, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SearchSource } from '@/lib/api'

interface SourcesTableProps {
  sources:        SearchSource[]
  cited:          Set<number>
  hoveredCite?:   number | null
  onRowHover?:    (n: number | null) => void
  mode?:          string
}

export function SourcesTable({
  sources,
  cited,
  hoveredCite,
  onRowHover,
  mode,
}: SourcesTableProps) {
  if (sources.length === 0) {
    return (
      <div className="rounded-xl bg-surface border border-border/8 px-5 py-8 text-center">
        <p className="text-sm text-foreground-3">
          Sources will appear here once you run a query.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <div className="px-5 py-3 flex items-center gap-2.5 border-b border-border/6">
        <Layers size={15} className="text-accent-blue" />
        <h3 className="text-sm font-medium text-foreground">Sources & Reranking</h3>
        <span className="text-[11px] text-foreground-3">{sources.length} retrieved</span>
        <div className="flex-1" />
        {mode && (
          <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase">
            mode: {mode}
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-high/40">
            <tr className="text-left text-[11px] font-mono text-foreground-3 tracking-[0.1em] uppercase">
              <th className="px-4 py-2.5 w-[3rem]">#</th>
              <th className="px-3 py-2.5">Filing</th>
              <th className="px-3 py-2.5">Snippet preview</th>
              <th className="px-3 py-2.5 w-[18%]">Scores</th>
              <th className="px-3 py-2.5 w-[3rem]"></th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => {
              const isHovered = hoveredCite === s.rank
              const isCited   = cited.has(s.rank)
              return (
                <tr
                  key={s.rank}
                  data-rank={s.rank}
                  onMouseEnter={() => onRowHover?.(s.rank)}
                  onMouseLeave={() => onRowHover?.(null)}
                  className={cn(
                    'border-t border-border/6 transition-colors',
                    isHovered && 'bg-accent-warm/5',
                    !isHovered && isCited && 'bg-accent-blue/[0.03]',
                  )}
                >
                  {/* # */}
                  <td className="px-4 py-3 align-top">
                    <span
                      className={cn(
                        'inline-flex items-center justify-center min-w-[1.5rem] h-[1.25rem] px-1.5',
                        'rounded-md text-[11px] font-mono font-semibold',
                        isCited
                          ? 'bg-accent-warm/15 text-accent-warm'
                          : 'bg-surface-high text-foreground-3',
                      )}
                    >
                      {s.rank}
                    </span>
                  </td>

                  {/* Filing */}
                  <td className="px-3 py-3 align-top">
                    <div className="font-medium text-foreground text-[13px] leading-tight">
                      {s.ticker} <span className="text-foreground-3">/</span> {s.filing_type}
                    </div>
                    <div className="text-[11px] font-mono text-foreground-3 mt-0.5">
                      period {s.period_of_report}
                    </div>
                    <div className="text-[10px] font-mono text-foreground-3/70 mt-0.5">
                      chunk #{s.chunk_index}
                    </div>
                  </td>

                  {/* Snippet */}
                  <td className="px-3 py-3 align-top text-foreground-2 text-[13px] leading-snug">
                    <p className="line-clamp-3 max-w-[40rem]">
                      {s.text.replace(/\s+/g, ' ').slice(0, 360)}
                    </p>
                  </td>

                  {/* Scores */}
                  <td className="px-3 py-3 align-top text-[11px] font-mono">
                    {s.rerank_score != null && (
                      <ScoreLine label="rerank" value={s.rerank_score} accent />
                    )}
                    {s.fused_score != null && (
                      <ScoreLine label="fused" value={s.fused_score} />
                    )}
                    {s.dense_score != null && (
                      <ScoreLine label="dense" value={s.dense_score} />
                    )}
                    {s.bm25_score != null && (
                      <ScoreLine label="bm25" value={s.bm25_score} />
                    )}
                  </td>

                  {/* Link */}
                  <td className="px-3 py-3 align-top">
                    <a
                      href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${s.ticker}&type=${s.filing_type}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-foreground-3 hover:text-foreground"
                      aria-label="Open filing on SEC EDGAR"
                      title="Open filing on SEC EDGAR"
                    >
                      <ExternalLink size={13} />
                    </a>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}


function ScoreLine({
  label,
  value,
  accent,
}: {
  label:   string
  value:   number
  accent?: boolean
}) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-foreground-3 w-[3rem]">{label}</span>
      <span className={cn(
        'tabular-nums',
        accent ? 'text-accent-warm font-semibold' : 'text-foreground-2',
      )}>
        {value.toFixed(3)}
      </span>
    </div>
  )
}
