import { useNavigate } from 'react-router-dom'
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { BondRow } from '../api/types'
import { CHART } from './chartTheme'

export type XDim = 'pd' | 'duration' | 'rating' | 'liquidity'

const RATING_ORDER = ['AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-', 'BB+', 'BB', 'BB-', 'B+', 'B', 'B-', 'CCC+', 'CCC']

const X_CONFIG: Record<XDim, { label: string; value: (b: BondRow) => number; fmt: (v: number) => string }> = {
  pd: { label: 'Merton PD (%)', value: (b) => b.merton_pd * 100, fmt: (v) => `${v.toFixed(2)}%` },
  duration: { label: 'Duration (yrs)', value: (b) => b.duration, fmt: (v) => v.toFixed(1) },
  rating: {
    label: 'Rating',
    value: (b) => RATING_ORDER.indexOf(b.rating),
    fmt: (v) => RATING_ORDER[Math.round(v)] ?? '',
  },
  liquidity: { label: 'Liquidity score', value: (b) => b.liquidity_score, fmt: (v) => v.toFixed(0) },
}

const LABEL_COLOR = { cheap: CHART.cheap, rich: CHART.rich, fair: '#5b6676' } as const

interface Props {
  bonds: BondRow[]
  xDim: XDim
  title?: string
}

/** Spread vs (PD | duration | rating | liquidity) scatter, colored by RV label. */
export function RvScatter({ bonds, xDim, title }: Props) {
  const navigate = useNavigate()
  const cfg = X_CONFIG[xDim]
  const data = bonds.map((b) => ({
    x: cfg.value(b),
    y: b.observed_spread * 10_000,
    cusip: b.cusip,
    issuer: b.issuer,
    label: b.rv_label,
    fill: LABEL_COLOR[b.rv_label],
  }))

  return (
    <div className="panel">
      <div className="panel-title">{title ?? `Spread vs ${cfg.label}`}</div>
      <div className="h-72 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="2 4" />
            <XAxis
              dataKey="x"
              type="number"
              name={cfg.label}
              tick={CHART.tick}
              stroke={CHART.grid}
              domain={['auto', 'auto']}
              tickFormatter={cfg.fmt}
              label={{ value: cfg.label, position: 'insideBottom', offset: -2, fill: CHART.text, fontSize: 10 }}
            />
            <YAxis
              dataKey="y"
              type="number"
              name="Spread"
              tick={CHART.tick}
              stroke={CHART.grid}
              tickFormatter={(v: number) => v.toFixed(0)}
              label={{ value: 'Spread (bps)', angle: -90, position: 'insideLeft', offset: 18, fill: CHART.text, fontSize: 10 }}
            />
            <Tooltip
              contentStyle={CHART.tooltipStyle}
              cursor={{ strokeDasharray: '3 3', stroke: CHART.axis }}
              content={({ payload }) => {
                const p = payload?.[0]?.payload as (typeof data)[number] | undefined
                if (!p) return null
                return (
                  <div style={CHART.tooltipStyle} className="px-2 py-1.5">
                    <div className="font-semibold" style={{ color: p.fill }}>
                      {p.issuer}
                    </div>
                    <div className="text-terminal-dim">{p.cusip}</div>
                    <div>
                      {cfg.fmt(p.x)} · {p.y.toFixed(0)}bps · {p.label}
                    </div>
                  </div>
                )
              }}
            />
            <Scatter
              data={data}
              onClick={(entry) => navigate(`/bond/${(entry as unknown as { cusip: string }).cusip}`)}
              cursor="pointer"
              animationDuration={350}
              shape={(props: unknown) => {
                const { cx, cy, payload } = props as { cx: number; cy: number; payload: { fill: string } }
                return <circle cx={cx} cy={cy} r={3} fill={payload.fill} fillOpacity={0.75} />
              }}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
