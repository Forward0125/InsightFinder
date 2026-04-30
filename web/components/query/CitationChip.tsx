'use client'

import { Fragment, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

const CITE_RE = /\[(\d+(?:\s*[,;]\s*\d+)*)\]/g

interface RenderArgs {
  text:     string
  onCite?:  (n: number) => void
  cited?:   Set<number>
  /** if set, this chip is currently highlighted (e.g. hover) */
  active?:  number | null
}

/** Convert "Foo grew 15% [3] and 20% [2,4]." into JSX with chips. */
export function renderAnswerWithCitations({
  text,
  onCite,
  cited,
  active,
}: RenderArgs): ReactNode {
  const parts: ReactNode[] = []
  let lastIdx = 0
  let key = 0

  // Use matchAll so we don't have to manage regex lastIndex state.
  for (const m of text.matchAll(CITE_RE)) {
    const idx = m.index ?? 0
    if (idx > lastIdx) {
      parts.push(<Fragment key={key++}>{text.slice(lastIdx, idx)}</Fragment>)
    }

    const numbers = m[1]
      .split(/[,;\s]+/)
      .map((s) => parseInt(s, 10))
      .filter((n) => Number.isFinite(n))

    parts.push(
      <span key={key++} className="inline-flex gap-px">
        {numbers.map((n) => (
          <CitationChip
            key={n}
            n={n}
            onCite={onCite}
            isCited={cited?.has(n) ?? true}
            isActive={active === n}
          />
        ))}
      </span>,
    )

    lastIdx = idx + m[0].length
  }

  if (lastIdx < text.length) {
    parts.push(<Fragment key={key++}>{text.slice(lastIdx)}</Fragment>)
  }

  return parts
}


function CitationChip({
  n,
  onCite,
  isCited,
  isActive,
}: {
  n:        number
  onCite?:  (n: number) => void
  isCited?: boolean
  isActive?: boolean
}) {
  const Tag: 'button' | 'span' = onCite ? 'button' : 'span'
  return (
    <Tag
      onClick={onCite ? () => onCite(n) : undefined}
      className={cn(
        'inline-flex items-center justify-center min-w-[1.25rem] px-1',
        'h-[1.125rem] rounded-md text-[10px] font-mono font-semibold leading-none',
        'mx-px align-baseline transition-colors',
        isActive
          ? 'bg-accent-warm text-white'
          : 'bg-accent-warm/15 text-accent-warm hover:bg-accent-warm/25',
        !isCited && 'opacity-60',
        onCite && 'cursor-pointer',
      )}
      aria-label={`Source ${n}`}
    >
      {n}
    </Tag>
  )
}
