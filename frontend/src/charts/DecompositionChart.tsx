import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { SpreadDecomposition } from '../api/types'
import { CHART } from './chartTheme'

/** Waterfall-style view of fair-spread components vs observed spread. */
export function DecompositionChart({ decomposition }: { decomposition: SpreadDecomposition }) {
  const d = decomposition
  const data = [
    { name: 'Default', value: d.default_component * 10_000, fill: CHART.blue },
    { name: 'Liquidity', value: d.liquidity_premium * 10_000, fill: CHART.purple },
    { name: 'Sector', value: d.sector_premium * 10_000, fill: '#38bdf8' },
    { name: 'Rating', value: d.rating_premium * 10_000, fill: '#818cf8' },
    { name: 'Fair', value: d.fair_spread * 10_000, fill: CHART.axis },
    { name: 'Observed', value: d.observed_spread * 10_000, fill: CHART.accent },
    {
      name: 'Residual',
      value: d.residual * 10_000,
      fill: d.residual > 0 ? CHART.cheap : CHART.rich,
    },
  ]

  return (
    <div className="panel">
      <div className="panel-title">Spread Decomposition (bps)</div>
      <div className="h-64 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="name" tick={CHART.tick} stroke={CHART.grid} interval={0} />
            <YAxis tick={CHART.tick} stroke={CHART.grid} tickFormatter={(v: number) => v.toFixed(0)} />
            <Tooltip
              contentStyle={CHART.tooltipStyle}
              cursor={{ fill: '#161d2880' }}
              formatter={(value) => [`${Number(value).toFixed(1)} bps`]}
            />
            <Bar dataKey="value" animationDuration={400} radius={[2, 2, 0, 0]}>
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
