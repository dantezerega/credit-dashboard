import { useState } from 'react'
import { CurveChart } from '../charts/CurveChart'
import { RvScatter, type XDim } from '../charts/RvScatter'
import { useCurve } from '../hooks/useApi'
import { useFilteredBonds } from '../hooks/useFilteredBonds'
import { FilterBar } from '../components/FilterBar'

const DIMS: { key: XDim; label: string }[] = [
  { key: 'pd', label: 'Spread vs PD' },
  { key: 'duration', label: 'Spread vs Duration' },
  { key: 'rating', label: 'Spread vs Rating' },
  { key: 'liquidity', label: 'Spread vs Liquidity' },
]

export function AnalyticsPage() {
  const { bonds, total } = useFilteredBonds()
  const { data: curve } = useCurve()
  const [primary, setPrimary] = useState<XDim>('pd')

  return (
    <div className="space-y-3 p-5">
      <FilterBar shown={bonds.length} total={total} />
      <div className="flex items-center gap-2">
        {DIMS.map((d) => (
          <button
            key={d.key}
            onClick={() => setPrimary(d.key)}
            className={`rounded-full border px-3.5 py-1.5 text-[11px] font-semibold tracking-wider uppercase transition-colors ${
              primary === d.key
                ? 'border-terminal-accent bg-terminal-accent/15 text-terminal-accent'
                : 'border-terminal-border text-terminal-dim hover:text-terminal-text'
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <RvScatter bonds={bonds} xDim={primary} />
        {curve && <CurveChart curve={curve} />}
        {DIMS.filter((d) => d.key !== primary).map((d) => (
          <RvScatter key={d.key} bonds={bonds} xDim={d.key} title={d.label} />
        ))}
      </div>
    </div>
  )
}
