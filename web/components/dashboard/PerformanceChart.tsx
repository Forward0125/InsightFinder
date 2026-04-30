'use client'

import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { TimeseriesPoint } from '@/lib/api'


interface PerformanceChartProps {
  data: TimeseriesPoint[]
}

export function PerformanceChart({ data }: PerformanceChartProps) {
  // Format day labels into MM-DD for x-axis brevity.
  const rows = data.map((p) => ({
    day:     p.day.slice(5),     // "MM-DD"
    queries: p.queries,
    p50:     p.p50_ms ?? 0,
    p95:     p.p95_ms ?? 0,
  }))

  return (
    <div className="rounded-xl bg-surface border border-border/8 overflow-hidden">
      <header className="px-5 py-3 border-b border-border/6">
        <h3 className="text-sm font-medium text-foreground">
          Query Performance Trends
        </h3>
        <p className="text-[11px] text-foreground-3 mt-0.5">
          Queries per day · p50 / p95 latency · last 7 days
        </p>
      </header>

      <div className="px-2 py-4 h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 12, right: 24, left: 8, bottom: 4 }}>
            <CartesianGrid
              strokeDasharray="2 4"
              stroke="rgb(255 255 255 / 0.06)"
            />
            <XAxis
              dataKey="day"
              tick={{ fill: 'rgb(145 142 135)', fontSize: 11, fontFamily: 'monospace' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              yAxisId="latency"
              orientation="left"
              tick={{ fill: 'rgb(145 142 135)', fontSize: 11, fontFamily: 'monospace' }}
              axisLine={false}
              tickLine={false}
              width={42}
              unit="ms"
            />
            <YAxis
              yAxisId="count"
              orientation="right"
              tick={{ fill: 'rgb(145 142 135)', fontSize: 11, fontFamily: 'monospace' }}
              axisLine={false}
              tickLine={false}
              width={28}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{
                background:    'rgb(18 18 34)',
                border:        '1px solid rgb(255 255 255 / 0.1)',
                borderRadius:  6,
                fontSize:      12,
              }}
              labelStyle={{ color: 'rgb(235 232 225)' }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 4 }}
              iconType="circle"
              iconSize={8}
            />
            <Line
              type="monotone"
              dataKey="p50"
              name="p50 latency"
              yAxisId="latency"
              stroke="rgb(59 130 246)"
              strokeWidth={1.75}
              dot={{ r: 2, strokeWidth: 0 }}
            />
            <Line
              type="monotone"
              dataKey="p95"
              name="p95 latency"
              yAxisId="latency"
              stroke="rgb(163 106 254)"
              strokeWidth={1.75}
              dot={{ r: 2, strokeWidth: 0 }}
            />
            <Line
              type="monotone"
              dataKey="queries"
              name="queries"
              yAxisId="count"
              stroke="rgb(52 211 153)"
              strokeWidth={1.5}
              strokeDasharray="3 3"
              dot={{ r: 2, strokeWidth: 0 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
