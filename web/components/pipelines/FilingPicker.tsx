'use client'

import { useEffect, useMemo, useState } from 'react'
import { X, Plus, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api, ApiError, type FilingChip } from '@/lib/api'


interface FilingPickerProps {
  isOpen:   boolean
  onClose:  () => void
  onPick:   (filing: FilingChip) => void
  /** Show a transient "rate limited" warning if set. */
  errorText?: string | null
}

/**
 * Modal listing the filings in data/raw/_index.csv. Visitor picks
 * one and we kick off a fresh ingestion run. Uses the same on-disk
 * file as the corpus (so no upload pipeline yet).
 */
export function FilingPicker({
  isOpen,
  onClose,
  onPick,
  errorText,
}: FilingPickerProps) {
  const [filings, setFilings] = useState<FilingChip[] | null>(null)
  const [loadErr, setLoadErr] = useState<string | null>(null)
  const [picked,  setPicked]  = useState<FilingChip | null>(null)
  const [tickerFilter, setTickerFilter] = useState<string>('')

  useEffect(() => {
    if (!isOpen || filings) return
    api.listFilings()
      .then(setFilings)
      .catch((err) => {
        setLoadErr(err instanceof ApiError ? err.message : 'load failed')
      })
  }, [isOpen, filings])

  // ESC closes
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])

  const tickers = useMemo(() => {
    if (!filings) return []
    return Array.from(new Set(filings.map((f) => f.ticker))).sort()
  }, [filings])

  const visibleFilings = useMemo(() => {
    if (!filings) return []
    return tickerFilter
      ? filings.filter((f) => f.ticker === tickerFilter)
      : filings
  }, [filings, tickerFilter])

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Pick a filing to ingest"
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-background/80 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className={cn(
        'w-full max-w-3xl max-h-[85vh] flex flex-col',
        'bg-surface border border-border/15 rounded-xl shadow-card-hover overflow-hidden',
      )}>
        {/* Header */}
        <header className="px-5 py-4 border-b border-border/6 flex items-center gap-3">
          <Plus size={16} className="text-accent-warm" />
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-medium text-foreground">New Pipeline Run</h2>
            <p className="text-[12px] text-foreground-3 mt-0.5">
              Pick a filing to re-ingest. The DAG below will animate live.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-foreground-3 hover:text-foreground hover:bg-surface-high"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </header>

        {errorText && (
          <div className="px-5 py-2.5 text-[12px] bg-amber-500/10 text-amber-400 border-b border-amber-500/20">
            {errorText}
          </div>
        )}

        {/* Ticker filter chips */}
        <div className="px-5 py-3 border-b border-border/6 flex items-center gap-2 overflow-x-auto">
          <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase shrink-0">
            ticker
          </span>
          <button
            onClick={() => setTickerFilter('')}
            className={chipCls(tickerFilter === '')}
          >
            All
          </button>
          {tickers.map((t) => (
            <button
              key={t}
              onClick={() => setTickerFilter(t)}
              className={chipCls(tickerFilter === t)}
            >
              {t}
            </button>
          ))}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loadErr ? (
            <p className="px-5 py-8 text-sm text-amber-400">{loadErr}</p>
          ) : !filings ? (
            <div className="px-5 py-8 text-sm text-foreground-3 inline-flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" /> loading filings…
            </div>
          ) : visibleFilings.length === 0 ? (
            <p className="px-5 py-8 text-sm text-foreground-3">No filings match.</p>
          ) : (
            <ul className="divide-y divide-border/6">
              {visibleFilings.map((f) => {
                const selected = picked?.local_path === f.local_path
                return (
                  <li key={f.local_path}>
                    <button
                      onClick={() => setPicked(f)}
                      className={cn(
                        'w-full text-left px-5 py-2.5 flex items-center gap-3',
                        'transition-colors hover:bg-surface-high',
                        selected && 'bg-accent-warm/[0.06]',
                      )}
                    >
                      <span className={cn(
                        'inline-flex items-center justify-center w-12 h-6 rounded',
                        'text-[11px] font-mono font-semibold',
                        selected
                          ? 'bg-accent-warm/20 text-accent-warm'
                          : 'bg-surface-high text-foreground-2',
                      )}>
                        {f.ticker}
                      </span>
                      <span className="text-[13px] font-medium text-foreground w-14">
                        {f.filing_type}
                      </span>
                      <span className="text-[12px] text-foreground-2 font-mono">
                        period {f.period_of_report}
                      </span>
                      <span className="flex-1" />
                      <span className="text-[11px] font-mono text-foreground-3">
                        {(f.size_bytes / 1024).toFixed(0)} KB
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Footer / pick button */}
        <footer className="px-5 py-3 border-t border-border/6 flex items-center justify-between gap-3">
          <p className="text-[11px] text-foreground-3">
            Limit: 5 ingestion runs per IP per hour.
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg text-[13px] text-foreground-2 hover:text-foreground hover:bg-surface-high"
            >
              Cancel
            </button>
            <button
              onClick={() => picked && onPick(picked)}
              disabled={!picked}
              className={cn(
                'px-3.5 py-1.5 rounded-lg text-[13px] font-medium',
                'bg-accent-warm text-white hover:bg-accent-violet',
                'disabled:bg-surface-high disabled:text-foreground-3',
                'transition-colors',
              )}
            >
              Start ingestion
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}


function chipCls(active: boolean): string {
  return cn(
    'shrink-0 px-2 py-0.5 rounded-md text-[11px] font-medium border',
    'transition-colors',
    active
      ? 'bg-accent-warm/15 border-accent-warm/30 text-accent-warm'
      : 'bg-surface-high border-border/8 text-foreground-2 hover:text-foreground',
  )
}
