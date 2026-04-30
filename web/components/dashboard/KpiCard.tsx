'use client'

import type { ComponentType } from 'react'
import { cn } from '@/lib/utils'

interface KpiCardProps {
  label:   string
  value:   string
  hint?:   string
  icon?:   ComponentType<{ size?: number; className?: string }>
  trend?:  'up' | 'down' | 'flat'
  trendText?: string
}

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  trend,
  trendText,
}: KpiCardProps) {
  return (
    <div className="p-5 rounded-xl bg-surface border border-border/8">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium text-foreground-2">{label}</p>
        {Icon && <Icon size={14} className="text-foreground-3" />}
      </div>
      <p className="mt-2 font-display text-3xl font-bold tabular-nums leading-none">
        {value}
      </p>
      <div className="mt-2 flex items-center gap-2 text-[10px] font-mono text-foreground-3 tracking-[0.1em] uppercase">
        {hint}
        {trend && trendText && (
          <span className={cn(
            'px-1.5 py-0.5 rounded normal-case font-mono tracking-normal',
            trend === 'up'   && 'text-emerald-400 bg-emerald-500/10',
            trend === 'down' && 'text-amber-400 bg-amber-500/10',
            trend === 'flat' && 'text-foreground-3 bg-surface-high',
          )}>
            {trend === 'up' ? '▲' : trend === 'down' ? '▼' : '·'} {trendText}
          </span>
        )}
      </div>
    </div>
  )
}
