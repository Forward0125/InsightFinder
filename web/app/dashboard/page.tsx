import { Container } from '@/components/ui/Container'

export const metadata = { title: 'Dashboard' }

export default function DashboardPage() {
  return (
    <Container size="full" className="py-8 md:py-12">
      <p className="text-[11px] font-mono text-foreground-3 tracking-[0.15em] uppercase mb-3">
        Dashboard
      </p>
      <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight">
        Real-time platform health.
      </h1>
      <p className="mt-3 text-foreground-2 max-w-2xl">
        KPIs, query performance trends, eval-gate health, and system alerts —
        all computed from live query traffic. UI ships in step 14.
      </p>

      <div className="mt-10 grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 max-w-5xl">
        {[
          { label: 'Average Response Time', value: '—',  hint: 'after step 10' },
          { label: 'Citations per Query',   value: '—',  hint: 'after step 10' },
          { label: 'Evaluation Pass Rate',  value: '—',  hint: 'after step 11' },
          { label: 'Active Queries',        value: '0',  hint: 'live' },
        ].map(({ label, value, hint }) => (
          <div key={label} className="p-5 rounded-xl bg-surface border border-border/8">
            <p className="text-xs font-medium text-foreground-2">{label}</p>
            <p className="mt-2 font-display text-3xl font-bold tabular-nums">{value}</p>
            <p className="mt-1 text-[10px] font-mono text-foreground-3 tracking-[0.1em] uppercase">
              {hint}
            </p>
          </div>
        ))}
      </div>
    </Container>
  )
}
