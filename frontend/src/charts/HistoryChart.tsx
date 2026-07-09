import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { HistoryPoint } from '../api/types'
import { shortDate } from '../utils/format'
import { CHART } from './chartTheme'

export interface Series {
  key: keyof HistoryPoint
  label: string
  color: string
  transform?: (v: number) => number
}

interface Props {
  title: string
  data: HistoryPoint[]
  series: Series[]
  unit?: string
  digits?: number
}

/** Generic multi-series time-series panel for bond history metrics. */
export function HistoryChart({ title, data, series, unit = '', digits = 1 }: Props) {
  const rows = data.map((d) => {
    const row: Record<string, string | number> = { date: d.as_of_date }
    for (const s of series) {
      const raw = d[s.key] as number
      row[s.key] = s.transform ? s.transform(raw) : raw
    }
    return row
  })

  return (
    <div className="panel">
      <div className="panel-title flex items-center justify-between">
        <span>{title}</span>
        {series.length > 1 && (
          <span className="flex gap-3 normal-case">
            {series.map((s) => (
              <span key={s.key} className="flex items-center gap-1 text-[10px] tracking-normal">
                <span className="inline-block h-[2px] w-3" style={{ background: s.color }} />
                <span className="text-terminal-dim">{s.label}</span>
              </span>
            ))}
          </span>
        )}
      </div>
      <div className="h-64 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="date"
              tick={CHART.tick}
              tickFormatter={shortDate}
              stroke={CHART.grid}
              minTickGap={48}
            />
            <YAxis
              tick={CHART.tick}
              stroke={CHART.grid}
              domain={['auto', 'auto']}
              tickFormatter={(v: number) => v.toFixed(digits)}
              width={58}
            />
            <Tooltip
              contentStyle={CHART.tooltipStyle}
              labelFormatter={(l) => shortDate(String(l))}
              formatter={(value, name) => [
                `${Number(value).toFixed(digits + 1)}${unit}`,
                series.find((s) => s.key === name)?.label ?? String(name),
              ]}
            />
            {series.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                stroke={s.color}
                strokeWidth={1.5}
                dot={false}
                animationDuration={350}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
