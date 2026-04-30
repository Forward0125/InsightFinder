'use client'

import {
  ReactFlow,
  Background,
  type Edge,
  type Node,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { useMemo } from 'react'
import {
  CheckCircle2, CircleDashed, Loader2, AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PipelineStatus, StepInfo, StepName } from '@/lib/api'

/**
 * Static DAG topology -- our pipeline is always the same 4 stages.
 * Positions are tuned so the chart fits a ~720x220 viewport.
 */
const NODE_DEFS: Array<{
  id:    string
  label: string
  step?: StepName            // maps to a row in pipeline_steps
  sub?:  string              // sub-label (e.g. "BM25 + pgvector")
  x:     number
  y:     number
}> = [
  { id: 'source',  label: 'Data Source',         x:  20, y:  90, sub: 'SEC EDGAR HTML' },
  { id: 'extract', label: 'Extract',  step: 'extract', x: 200, y:  90, sub: 'selectolax' },
  { id: 'chunk',   label: 'Chunk',    step: 'chunk',   x: 380, y:  90, sub: '~500-tok windows' },
  { id: 'embed',   label: 'Embed',    step: 'embed',   x: 560, y:  20, sub: 'OpenAI dense' },
  { id: 'bm25',    label: 'BM25 Index',                x: 560, y: 160, sub: 'tsvector / GIN' },
  { id: 'index',   label: 'Vector Store', step: 'index', x: 760, y:  90, sub: 'pgvector / HNSW' },
]

const EDGES: Array<{ from: string; to: string }> = [
  { from: 'source',  to: 'extract' },
  { from: 'extract', to: 'chunk'   },
  { from: 'chunk',   to: 'embed'   },
  { from: 'chunk',   to: 'bm25'    },
  { from: 'embed',   to: 'index'   },
  { from: 'bm25',    to: 'index'   },
]


/* ─── Custom node ──────────────────────────────────────────── */

interface NodeData extends Record<string, unknown> {
  label:  string
  sub?:   string
  status: PipelineStatus | 'idle'
  progress: number
  meta?:  Record<string, unknown> | null
}

import { Handle, Position } from '@xyflow/react'

function StageNode({ data }: { data: NodeData }) {
  const { label, sub, status, progress, meta } = data

  const Icon =
    status === 'success' ? CheckCircle2
    : status === 'running' ? Loader2
    : status === 'failed' ? AlertCircle
    : CircleDashed

  return (
    <div className={cn(
      'relative w-44 rounded-lg border bg-surface',
      'transition-colors',
      status === 'success' && 'border-emerald-400/30',
      status === 'running' && 'border-accent-warm/40',
      status === 'failed'  && 'border-amber-400/40',
      (status === 'queued' || status === 'idle') && 'border-border/10',
    )}>
      {/* Handles -- positions match the edge connections */}
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-foreground-3/40 !border-0 !w-1.5 !h-1.5"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-foreground-3/40 !border-0 !w-1.5 !h-1.5"
      />

      <div className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Icon
            size={13}
            className={cn(
              status === 'success' && 'text-emerald-400',
              status === 'running' && 'text-accent-warm animate-spin',
              status === 'failed'  && 'text-amber-400',
              (status === 'queued' || status === 'idle') && 'text-foreground-3',
            )}
          />
          <span className="text-[12px] font-medium text-foreground">
            {label}
          </span>
        </div>
        {sub && (
          <p className="text-[10px] font-mono text-foreground-3 mt-0.5 ml-[19px]">
            {sub}
          </p>
        )}

        {/* Progress bar */}
        {(status === 'running' || (status === 'success' && progress > 0)) && (
          <div className="mt-2 h-1 rounded-full bg-surface-high overflow-hidden">
            <div
              className={cn(
                'h-full transition-[width] duration-300',
                status === 'success'
                  ? 'bg-emerald-400/70'
                  : 'bg-gradient-to-r from-accent-blue to-accent-warm',
              )}
              style={{ width: `${progress}%` }}
            />
          </div>
        )}

        {/* Metadata footer */}
        {meta && status === 'success' && (
          <div className="mt-1.5 text-[10px] font-mono text-foreground-3/80">
            {formatMeta(meta)}
          </div>
        )}
      </div>
    </div>
  )
}


function formatMeta(meta: Record<string, unknown>): string {
  // Show the most useful 1-2 fields per step type.
  const parts: string[] = []
  if (typeof meta.chars === 'number')    parts.push(`${(meta.chars / 1000).toFixed(0)}k chars`)
  if (typeof meta.chunks === 'number')   parts.push(`${meta.chunks} chunks`)
  if (typeof meta.tokens === 'number')   parts.push(`${meta.tokens.toLocaleString()} tok`)
  if (typeof meta.n === 'number')        parts.push(`n=${meta.n}`)
  if (typeof meta.cost_usd === 'number') parts.push(`$${(meta.cost_usd as number).toFixed(4)}`)
  if (typeof meta.seconds === 'number')  parts.push(`${(meta.seconds as number).toFixed(2)}s`)
  return parts.slice(0, 2).join(' · ')
}


const NODE_TYPES: NodeTypes = { stage: StageNode }


/* ─── Public DAG ───────────────────────────────────────────── */

interface PipelineDAGProps {
  /** Per-step state, keyed by step name. */
  steps: Partial<Record<StepName, StepInfo>>
  /** Overall run status -- used to color the unmapped "Data Source" node. */
  runStatus?: PipelineStatus | 'idle'
}

export function PipelineDAG({ steps, runStatus = 'idle' }: PipelineDAGProps) {
  const { nodes, edges } = useMemo<{ nodes: Node<NodeData>[]; edges: Edge[] }>(() => {
    const flowNodes: Node<NodeData>[] = NODE_DEFS.map((def) => {
      let status: PipelineStatus | 'idle'
      let progress = 0
      let meta: Record<string, unknown> | null = null

      if (def.id === 'source') {
        // "Data Source" lights up green once any step has started.
        const anyStarted = Object.values(steps).some(
          (s) => s && s.status !== 'queued',
        )
        status = anyStarted ? 'success' : (runStatus === 'idle' ? 'idle' : 'queued')
        progress = anyStarted ? 100 : 0
      } else if (def.id === 'bm25') {
        // BM25 is a logical node -- tracks the index step's status (since
        // the tsvector is a generated column written by index).
        const indexStep = steps.index
        status = indexStep?.status ?? 'queued'
        progress = indexStep?.progress_pct ?? 0
      } else if (def.step) {
        const s = steps[def.step]
        status = s?.status ?? 'queued'
        progress = s?.progress_pct ?? 0
        meta = (s?.metadata as Record<string, unknown> | null) ?? null
      } else {
        status = 'idle'
      }

      return {
        id: def.id,
        type: 'stage',
        position: { x: def.x, y: def.y },
        data: { label: def.label, sub: def.sub, status, progress, meta },
        draggable: false,
        selectable: false,
      }
    })

    const flowEdges: Edge[] = EDGES.map(({ from, to }) => {
      const target = flowNodes.find((n) => n.id === to)
      const active =
        target?.data.status === 'running' ||
        target?.data.status === 'success'
      return {
        id: `${from}-${to}`,
        source: from,
        target: to,
        animated: target?.data.status === 'running',
        style: {
          stroke: active
            ? 'rgb(163, 106, 254)'      // accent-warm
            : 'rgb(255 255 255 / 0.14)',
          strokeWidth: 1.5,
        },
      }
    })

    return { nodes: flowNodes, edges: flowEdges }
  }, [steps, runStatus])

  return (
    <div className="h-[260px] rounded-lg border border-border/8 bg-surface overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        proOptions={{ hideAttribution: true }}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        nodesDraggable={false}
        nodesConnectable={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        panOnDrag={false}
        zoomOnDoubleClick={false}
      >
        <Background gap={20} size={1} color="rgb(255 255 255 / 0.04)" />
      </ReactFlow>
    </div>
  )
}
