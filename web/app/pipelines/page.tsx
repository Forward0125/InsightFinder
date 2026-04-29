import { Container } from '@/components/ui/Container'

export const metadata = { title: 'Pipelines' }

export default function PipelinesPage() {
  return (
    <Container size="full" className="py-8 md:py-12">
      <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-3">
        Pipelines
      </p>
      <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight">
        Document ingestion as a DAG.
      </h1>
      <p className="mt-3 text-foreground-2 max-w-2xl">
        Knowledge bases, indexing pipelines, and live progress streaming.
        UI ships in step 13 — backend ingestion ships in steps 7–8.
      </p>

      <div className="mt-10 p-8 rounded-xl bg-surface border border-border/8 max-w-2xl">
        <p className="text-sm text-foreground-3 font-mono">
          $ alembic upgrade head{'\n'}
          ✓ schema applied{'\n'}
          ⏳ ingestion pipeline pending
        </p>
      </div>
    </Container>
  )
}
