'use client'

import { Search, Sparkles, Filter, RotateCw } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import type { SearchMode } from '@/lib/api'

const MODE_OPTIONS: { value: SearchMode; label: string; hint: string }[] = [
  { value: 'bm25',          label: 'BM25',          hint: 'Postgres FTS only — keyword matching' },
  { value: 'dense',         label: 'Dense',         hint: 'pgvector cosine similarity' },
  { value: 'hybrid',        label: 'Hybrid',        hint: 'BM25 + dense via RRF (default)' },
  { value: 'hybrid_rerank', label: 'Hybrid + Rerank', hint: 'Adds local cross-encoder (slow on CPU)' },
]

export interface QueryInputProps {
  onSubmit: (query: string, mode: SearchMode) => void
  disabled: boolean
  initialQuery?: string
  initialMode?: SearchMode
}

export function QueryInput({
  onSubmit,
  disabled,
  initialQuery = '',
  initialMode  = 'hybrid',
}: QueryInputProps) {
  const [query, setQuery] = useState(initialQuery)
  const [mode,  setMode]  = useState<SearchMode>(initialMode)

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!query.trim() || disabled) return
        onSubmit(query.trim(), mode)
      }}
      className="space-y-3"
    >
      <div className="relative">
        <Search
          size={18}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-foreground-3 pointer-events-none"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={disabled}
          placeholder="Ask the filings — e.g. What was Apple's iPhone revenue in fiscal Q1 2026?"
          className={cn(
            'w-full pl-11 pr-32 py-3.5 rounded-xl text-[15px]',
            'bg-surface border border-border/10',
            'text-foreground placeholder:text-foreground-3',
            'focus:outline-none focus:border-accent-warm/40',
            'disabled:opacity-60',
            'transition-colors',
          )}
        />
        <button
          type="submit"
          disabled={disabled || !query.trim()}
          className={cn(
            'absolute right-2 top-1/2 -translate-y-1/2',
            'inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg',
            'text-[13px] font-medium',
            'bg-accent-warm text-white hover:bg-accent-violet',
            'disabled:bg-surface-high disabled:text-foreground-3',
            'transition-colors',
          )}
        >
          {disabled ? (
            <>
              <RotateCw size={13} className="animate-spin" />
              Working
            </>
          ) : (
            <>
              <Sparkles size={13} />
              Ask
            </>
          )}
        </button>
      </div>

      {/* Mode selector — chips. Keyboard-accessible radio. */}
      <div
        className="flex items-center gap-2 flex-wrap"
        role="radiogroup"
        aria-label="Retrieval mode"
      >
        <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase mr-1">
          <Filter size={11} className="inline -mt-0.5 mr-1" />
          Mode
        </span>
        {MODE_OPTIONS.map(({ value, label, hint }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={mode === value}
            title={hint}
            onClick={() => setMode(value)}
            disabled={disabled}
            className={cn(
              'px-2.5 py-1 rounded-md text-[11px] font-medium border',
              'transition-colors duration-150 disabled:opacity-50',
              mode === value
                ? 'bg-accent-warm/15 border-accent-warm/30 text-accent-warm'
                : 'bg-surface border-border/10 text-foreground-2 hover:text-foreground hover:bg-surface-high',
            )}
          >
            {label}
          </button>
        ))}
      </div>
    </form>
  )
}
