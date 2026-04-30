'use client'

import { Terminal, Trash2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

export type LogLevel = 'INFO' | 'DEBUG' | 'WARN' | 'ERROR'

export interface LogLine {
  ts:    number
  level: LogLevel
  text:  string
}


interface SystemLogsProps {
  lines:    LogLine[]
  onClear?: () => void
}

/**
 * Renders a scrolling log panel matching the screenshot's
 * "[INFO] Hybrid retrieval initiated" style. The parent feeds it
 * lines derived from SSE events so it reflects real activity.
 */
export function SystemLogs({ lines, onClear }: SystemLogsProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new lines arrive.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines])

  return (
    <section
      aria-label="System logs"
      className="rounded-xl bg-surface border border-border/8 overflow-hidden flex flex-col"
    >
      <header className="px-4 py-2.5 flex items-center justify-between border-b border-border/6">
        <div className="inline-flex items-center gap-1.5">
          <Terminal size={12} className="text-foreground-3" />
          <h4 className="text-[12px] font-medium text-foreground">System Logs</h4>
        </div>
        {lines.length > 0 && onClear && (
          <button
            onClick={onClear}
            className="text-[11px] text-foreground-3 hover:text-foreground inline-flex items-center gap-1"
            title="Clear logs"
          >
            <Trash2 size={11} />
          </button>
        )}
      </header>

      <div
        ref={scrollRef}
        className="px-4 py-3 max-h-[18rem] overflow-y-auto font-mono text-[11px] leading-[1.7]"
      >
        {lines.length === 0 ? (
          <p className="text-foreground-3 italic">no activity yet</p>
        ) : (
          lines.map((l, i) => (
            <div key={i} className="flex gap-2 text-foreground-2">
              <span className={cn('shrink-0 w-12', LEVEL_COLOR[l.level])}>
                [{l.level}]
              </span>
              <span className="shrink-0 text-foreground-3/70 w-16">
                {fmtTime(l.ts)}
              </span>
              <span className="break-words">{l.text}</span>
            </div>
          ))
        )}
      </div>
    </section>
  )
}


const LEVEL_COLOR: Record<LogLevel, string> = {
  INFO:  'text-accent-blue',
  DEBUG: 'text-foreground-3',
  WARN:  'text-amber-400',
  ERROR: 'text-rose-400',
}


function fmtTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false }).slice(0, 8)
}
