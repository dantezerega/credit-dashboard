import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { CurveResponse } from '../api/types'
import { CHART } from './chartTheme'

interface Props {
  curve: CurveResponse
  /** Optional marker: bond yield at its maturity, drawn against the curve. */
  bondPoint?: { maturity: number; ytm: number; label: string }
}

export function CurveChart({ curve, bondPoint }: Props) {
  const data = curve.points.map((p) => ({
    tenor: p.tenor,
    label: p.tenor_label,
    par: p.par_yield * 100,
    zero: p.zero_rate * 100,
  }))

  return (
    <div className="panel">
      <div className="panel-title flex items-center justify-between">
        <span>Treasury Curve — {curve.as_of_date}</span>
        <span className="flex gap-3 normal-case">
          <span className="flex items-center gap-1 text-[10px]">
            <span className="inline-block h-[2px] w-3" style={{ background: CHART.accent }} />
            <span className="text-terminal-dim">Par</span>
          </span>
          <span className="flex items-center gap-1 text-[10px]">
            <span className="inline-block h-[2px] w-3" style={{ background: CHART.blue }} />
            <span className="text-terminal-dim">Zero</span>
          </span>
          {bondPoint && (
            <span className="flex items-center gap-1 text-[10px]">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: CHART.cheap }} />
              <span className="text-terminal-dim">{bondPoint.label}</span>
            </span>
          )}
        </span>
      </div>
      <div className="h-64 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="tenor"
              type="number"
              scale="sqrt"
              domain={[0, 30]}
              ticks={[0.25, 1, 2, 5, 10, 20, 30]}
              tick={CHART.tick}
              stroke={CHART.grid}
              tickFormatter={(t: number) => (t < 1 ? `${Math.round(t * 12)}M` : `${t}Y`)}
            />
            <YAxis
              tick={CHART.tick}
              stroke={CHART.grid}
              domain={['auto', 'auto']}
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            />
            <Tooltip
              contentStyle={CHART.tooltipStyle}
              formatter={(value, name) => [`${Number(value).toFixed(3)}%`, name === 'par' ? 'Par yield' : 'Zero rate']}
              labelFormatter={(t) => `${t}Y`}
            />
            <Line type="monotone" dataKey="par" stroke={CHART.accent} strokeWidth={1.5} dot={{ r: 2 }} animationDuration={350} />
            <Line type="monotone" dataKey="zero" stroke={CHART.blue} strokeWidth={1.5} dot={false} animationDuration={350} />
            {bondPoint && (
              <ReferenceDot
                x={Math.min(bondPoint.maturity, 30)}
                y={bondPoint.ytm * 100}
                r={4}
                fill={CHART.cheap}
                stroke="none"
                ifOverflow="extendDomain"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
