'use client'

import { MessageSquare, Loader2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { renderAnswerWithCitations } from './CitationChip'

interface AnswerCardProps {
  answer:     string
  cited:      Set<number>
  status:     'idle' | 'streaming' | 'completed' | 'error'
  onCiteClick?: (n: number) => void
  hoveredCite?: number | null
  errorText?: string | null
}

export function AnswerCard({
  answer,
  cited,
  status,
  onCiteClick,
  hoveredCite,
  errorText,
}: AnswerCardProps) {
  const isStreaming = status === 'streaming'
  const isError     = status === 'error'

  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 flex items-center gap-2.5 border-b border-border/6">
        <MessageSquare size={15} className="text-accent-blue" />
        <h3 className="text-sm font-medium text-foreground">Generated Answer</h3>
        <div className="flex-1" />
        <span className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase">
          {status === 'idle' && 'awaiting query'}
          {status === 'streaming' && (
            <span className="inline-flex items-center gap-1.5">
              <Loader2 size={11} className="animate-spin" />
              streaming
            </span>
          )}
          {status === 'completed' && 'completed'}
          {status === 'error' && (
            <span className="inline-flex items-center gap-1.5 text-amber-400">
              <AlertCircle size={11} />
              error
            </span>
          )}
        </span>
      </div>

      {/* Body */}
      <div className="px-5 py-5 min-h-[5rem]">
        {isError && (
          <p className="text-sm text-amber-400">
            {errorText || 'Something went wrong.'}
          </p>
        )}

        {!isError && (
          <p className={cn(
            'text-[15px] leading-[1.7] text-foreground-2 whitespace-pre-wrap',
            'text-pretty',
          )}>
            {answer ? (
              <>
                {renderAnswerWithCitations({
                  text:    answer,
                  onCite:  onCiteClick,
                  cited:   cited,
                  active:  hoveredCite ?? null,
                })}
                {isStreaming && (
                  <span
                    className="inline-block w-[6px] h-[1.05em] bg-accent-warm/80 align-text-bottom ml-0.5 animate-pulse"
                    aria-hidden
                  />
                )}
              </>
            ) : (
              <span className="text-foreground-3 italic">
                {status === 'idle'
                  ? 'Enter a question above to get a cited answer from SEC filings.'
                  : 'Retrieving sources…'}
              </span>
            )}
          </p>
        )}
      </div>
    </div>
  )
}
