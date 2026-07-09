import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { CashFlowItem } from '../api/types'
import { shortDate } from '../utils/format'
import { CHART } from './chartTheme'

export function CashflowChart({ cashflows }: { cashflows: CashFlowItem[] }) {
  const data = cashflows.map((cf) => ({
    date: cf.date,
    amount: cf.amount,
    kind: cf.kind,
  }))

  return (
    <div className="panel">
      <div className="panel-title">Cash Flow Schedule (per 100 face)</div>
      <div className="h-64 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -14 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="date" tick={CHART.tick} stroke={CHART.grid} tickFormatter={shortDate} minTickGap={40} />
            <YAxis tick={CHART.tick} stroke={CHART.grid} scale="sqrt" domain={[0, 'auto']} />
            <Tooltip
              contentStyle={CHART.tooltipStyle}
              cursor={{ fill: '#161d2880' }}
              labelFormatter={(l) => shortDate(String(l))}
              formatter={(value, _n, item) => [
                `${Number(value).toFixed(3)} — ${(item?.payload as { kind: string }).kind}`,
                'Amount',
              ]}
            />
            <Bar dataKey="amount" animationDuration={400} radius={[2, 2, 0, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.kind === 'coupon' ? CHART.blue : CHART.accent} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
