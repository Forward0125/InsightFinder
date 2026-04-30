'use client'

import { useEffect, useState } from 'react'
import { Clock, X } from 'lucide-react'
import { cn } from '@/lib/utils'

const STORAGE_KEY = 'insightfinder.history.v1'
const MAX_ENTRIES = 8

export interface HistoryEntry {
  query:   string
  mode:    string
  ts:      number       // unix ms
  cost?:   number
  passed?: boolean      // gates_passed
}

/** Read history from localStorage. */
export function readHistory(): HistoryEntry[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.slice(0, MAX_ENTRIES) : []
  } catch {
    return []
  }
}

/** Append to history, dedupe consecutive duplicates, keep MAX_ENTRIES. */
export function pushHistory(entry: HistoryEntry): HistoryEntry[] {
  const current = readHistory()
  const existing = current.filter((e) => e.query !== entry.query)
  const next = [entry, ...existing].slice(0, MAX_ENTRIES)
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    /* storage full / disabled — silently no-op */
  }
  return next
}


interface QueryHistoryProps {
  /** Bumped by the parent to nudge re-read after each run. */
  version?:    number
  onSelect?:   (query: string) => void
}

export function QueryHistory({ version = 0, onSelect }: QueryHistoryProps) {
  const [entries, setEntries] = useState<HistoryEntry[]>([])

  // Read on mount and whenever `version` changes.
  useEffect(() => {
    setEntries(readHistory())
  }, [version])

  const clear = () => {
    try { window.localStorage.removeItem(STORAGE_KEY) } catch { /* */ }
    setEntries([])
  }

  return (
    <section
      aria-label="Query history"
      className="rounded-xl bg-surface border border-border/8 overflow-hidden"
    >
      <header className="px-4 py-2.5 flex items-center justify-between border-b border-border/6">
        <div className="inline-flex items-center gap-1.5">
          <Clock size={12} className="text-foreground-3" />
          <h4 className="text-[12px] font-medium text-foreground">Query History</h4>
        </div>
        {entries.length > 0 && (
          <button
            onClick={clear}
            className="text-[11px] text-foreground-3 hover:text-foreground inline-flex items-center gap-1"
          >
            <X size={11} /> clear
          </button>
        )}
      </header>

      {entries.length === 0 ? (
        <p className="px-4 py-4 text-[11px] text-foreground-3 italic text-center">
          your queries will appear here
        </p>
      ) : (
        <ul className="divide-y divide-border/6">
          {entries.map((e, i) => (
            <li key={i}>
              <button
                onClick={() => onSelect?.(e.query)}
                className={cn(
                  'w-full text-left px-4 py-2.5',
                  'hover:bg-surface-high transition-colors',
                )}
              >
                <p className="text-[12px] text-foreground line-clamp-2 leading-snug">
                  {e.query}
                </p>
                <div className="flex items-center gap-2 mt-1 text-[10px] font-mono text-foreground-3">
                  <span>{relativeTime(e.ts)}</span>
                  <span>·</span>
                  <span>{e.mode}</span>
                  {e.passed != null && (
                    <span className={cn(
                      'px-1 rounded',
                      e.passed ? 'text-emerald-400' : 'text-amber-400',
                    )}>
                      {e.passed ? 'PASS' : 'FAIL'}
                    </span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}


function relativeTime(ts: number): string {
  const sec = Math.max(1, Math.round((Date.now() - ts) / 1000))
  if (sec < 60) return `${sec}s ago`
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`
  return `${Math.round(sec / 86400)}d ago`
}
