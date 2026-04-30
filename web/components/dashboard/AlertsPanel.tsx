'use client'

import { Info, AlertTriangle, AlertOctagon } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AlertRow } from '@/lib/api'


interface AlertsPanelProps {
  alerts: AlertRow[]
}

export function AlertsPanel({ alerts }: AlertsPanelProps) {
  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6">
        <h3 className="text-sm font-medium text-foreground">
          System Status &amp; Alerts
        </h3>
        <p className="text-[11px] text-foreground-3 mt-0.5">
          Recent events from ingestion, eval, and search
        </p>
      </header>

      {alerts.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-foreground-3">
          All quiet — no alerts in the feed.
        </p>
      ) : (
        <ul className="divide-y divide-border/6">
          {alerts.map((a) => (
            <li key={a.id} className="px-5 py-3">
              <div className="flex items-start gap-3">
                <SeverityIcon severity={a.severity} />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-foreground leading-snug">
                    {a.title}
                  </p>
                  {a.body && (
                    <p className="mt-0.5 text-[11px] font-mono text-foreground-2 leading-snug break-words">
                      {a.body}
                    </p>
                  )}
                  <div className="mt-1 flex items-center gap-2 text-[10px] font-mono text-foreground-3">
                    {a.source && <span>source: {a.source}</span>}
                    {a.created_at && (
                      <>
                        <span>·</span>
                        <span>{relativeTime(a.created_at)}</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}


function SeverityIcon({ severity }: { severity: AlertRow['severity'] }) {
  const cls = cn(
    'shrink-0 mt-0.5',
    severity === 'info'    && 'text-accent-blue',
    severity === 'warning' && 'text-amber-400',
    severity === 'error'   && 'text-rose-400',
  )
  if (severity === 'error')   return <AlertOctagon  size={14} className={cls} />
  if (severity === 'warning') return <AlertTriangle size={14} className={cls} />
  return <Info size={14} className={cls} />
}


function relativeTime(iso: string): string {
  const t = new Date(iso).getTime()
  const sec = Math.max(1, Math.round((Date.now() - t) / 1000))
  if (sec < 60)    return `${sec}s ago`
  if (sec < 3600)  return `${Math.round(sec / 60)}m ago`
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`
  return `${Math.round(sec / 86400)}d ago`
}
