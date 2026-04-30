'use client'

import { ShieldCheck, Loader2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { EvalEvent } from '@/lib/api'

interface EvalGatesCardProps {
  evaluation: EvalEvent | null
  /** True while we're awaiting the eval event. */
  pending:    boolean
}

const GATES = [
  {
    key:        'faithfulness'      as const,
    label:      'Faithfulness',
    direction:  'higher' as const,
    threshold:  0.70,
  },
  {
    key:        'answer_relevance'  as const,
    label:      'Answer Relevance',
    direction:  'higher' as const,
    threshold:  0.70,
  },
  {
    key:        'hallucination_risk' as const,
    label:      'Hallucination Risk',
    direction:  'lower' as const,
    threshold:  0.30,
  },
]

export function EvalGatesCard({ evaluation, pending }: EvalGatesCardProps) {
  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <div className="px-5 py-3 flex items-center gap-2.5 border-b border-border/6">
        <ShieldCheck size={15} className="text-accent-blue" />
        <h3 className="text-sm font-medium text-foreground">Evaluation Gates</h3>
        <div className="flex-1" />
        {evaluation && (
          <span className={cn(
            'text-[10px] font-mono tracking-[0.15em] uppercase px-2 py-0.5 rounded',
            evaluation.gates_passed
              ? 'text-emerald-400 bg-emerald-500/10'
              : 'text-amber-400 bg-amber-500/10',
          )}>
            {evaluation.gates_passed ? 'all pass' : 'fail'}
          </span>
        )}
        {pending && (
          <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase inline-flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin" />
            scoring
          </span>
        )}
      </div>

      <div className="px-5 py-4 space-y-4">
        {GATES.map(({ key, label, direction, threshold }) => {
          const value = evaluation?.[key] ?? null
          const passed = value == null
            ? null
            : direction === 'higher'
              ? value >= threshold
              : value <= threshold
          return (
            <ScoreRow
              key={key}
              label={label}
              value={value}
              direction={direction}
              threshold={threshold}
              passed={passed}
              pending={pending}
            />
          )
        })}

        {evaluation?.reasoning && (
          <div className="pt-3 border-t border-border/6">
            <p className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-1.5">
              Reasoning
            </p>
            <p className="text-[12px] text-foreground-2 leading-snug">
              {evaluation.reasoning}
            </p>
          </div>
        )}

        {!evaluation && !pending && (
          <p className="text-[12px] text-foreground-3 text-center py-2">
            Eval runs after the answer streams.
          </p>
        )}
      </div>
    </div>
  )
}


function ScoreRow({
  label,
  value,
  direction,
  threshold,
  passed,
  pending,
}: {
  label:     string
  value:     number | null
  direction: 'higher' | 'lower'
  threshold: number
  passed:    boolean | null
  pending:   boolean
}) {
  const pct = value == null ? 0 : Math.round(value * 100)
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-[13px] font-medium text-foreground-2">{label}</span>
        <div className="flex items-baseline gap-2">
          {value != null && (
            <span className="text-[14px] font-display font-semibold tabular-nums text-foreground">
              {value.toFixed(2)}
            </span>
          )}
          {passed != null && (
            <span className={cn(
              'text-[10px] font-mono tracking-[0.15em] uppercase px-1.5 py-0.5 rounded',
              passed
                ? 'text-emerald-400 bg-emerald-500/10'
                : 'text-amber-400 bg-amber-500/10',
            )}>
              {direction === 'lower' ? (passed ? 'low' : 'high') : (passed ? 'pass' : 'fail')}
            </span>
          )}
          {value == null && pending && (
            <Loader2 size={11} className="text-foreground-3 animate-spin" />
          )}
        </div>
      </div>

      {/* Score bar */}
      <div className="relative h-1.5 rounded-full bg-surface-high overflow-hidden">
        {/* Threshold marker */}
        <div
          aria-hidden
          className="absolute top-0 bottom-0 w-px bg-foreground-3/40"
          style={{ left: `${threshold * 100}%` }}
        />
        {/* Fill */}
        <div
          className={cn(
            'absolute top-0 left-0 bottom-0 transition-[width] duration-500 ease-out',
            value == null
              ? 'bg-surface-high'
              : passed
                ? 'bg-gradient-to-r from-accent-blue to-accent-warm'
                : 'bg-amber-500/60',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1.5 text-[10px] font-mono text-foreground-3 tracking-wide">
        threshold {direction === 'higher' ? '≥' : '≤'} {threshold.toFixed(2)}
      </p>
    </div>
  )
}
