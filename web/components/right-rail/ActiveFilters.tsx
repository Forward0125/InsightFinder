'use client'

import { ChevronDown, X } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

/**
 * UI-only filter pane (matches screenshot 02_1.webp). Wired to actual
 * retrieval in step 14 — for now it just records selections in
 * component state for future use.
 */
export function ActiveFilters() {
  const [docType,  setDocType]  = useState<'all' | '10-K' | '10-Q'>('all')
  const [dateRange, setDateRange] = useState<'all' | '1y' | '6m' | '3m'>('all')

  return (
    <section
      aria-label="Active filters"
      className="rounded-xl bg-surface border border-border/8 overflow-hidden"
    >
      <header className="px-4 py-2.5 flex items-center justify-between border-b border-border/6">
        <h4 className="text-[12px] font-medium text-foreground">Active Filters</h4>
        {(docType !== 'all' || dateRange !== 'all') && (
          <button
            onClick={() => { setDocType('all'); setDateRange('all') }}
            className="text-[11px] text-foreground-3 hover:text-foreground inline-flex items-center gap-1"
          >
            <X size={11} /> reset
          </button>
        )}
      </header>

      <div className="px-4 py-3 space-y-3">
        <FilterSelect
          label="Document Type"
          value={docType}
          onChange={(v) => setDocType(v as typeof docType)}
          options={[
            { value: 'all',  label: 'All filings' },
            { value: '10-K', label: '10-K (annual)' },
            { value: '10-Q', label: '10-Q (quarterly)' },
          ]}
        />
        <FilterSelect
          label="Date Range"
          value={dateRange}
          onChange={(v) => setDateRange(v as typeof dateRange)}
          options={[
            { value: 'all', label: 'All time' },
            { value: '1y',  label: 'Last 12 months' },
            { value: '6m',  label: 'Last 6 months' },
            { value: '3m',  label: 'Last 3 months' },
          ]}
        />
        <p className="text-[10px] text-foreground-3 italic">
          Wired in step 14.
        </p>
      </div>
    </section>
  )
}


function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label:    string
  value:    string
  onChange: (v: string) => void
  options:  { value: string; label: string }[]
}) {
  return (
    <label className="block">
      <span className="block text-[10px] font-mono text-foreground-3 tracking-[0.12em] uppercase mb-1">
        {label}
      </span>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            'appearance-none w-full px-3 py-2 pr-8 rounded-lg',
            'bg-surface-high border border-border/10 text-[13px] text-foreground',
            'focus:outline-none focus:border-accent-warm/40',
          )}
        >
          {options.map(({ value: v, label }) => (
            <option key={v} value={v}>{label}</option>
          ))}
        </select>
        <ChevronDown
          size={14}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-foreground-3 pointer-events-none"
        />
      </div>
    </label>
  )
}
