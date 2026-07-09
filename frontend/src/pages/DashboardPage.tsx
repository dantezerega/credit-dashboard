import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BondTable } from '../components/BondTable'
import { FilterBar } from '../components/FilterBar'
import { StatCard } from '../components/StatCard'
import { useDashboard } from '../hooks/useApi'
import { useFilteredBonds } from '../hooks/useFilteredBonds'
import { useFilterStore } from '../store/filterStore'
import { useUiStore } from '../store/uiStore'
import { num } from '../utils/format'

export function DashboardPage() {
  const { bonds, isLoading, total } = useFilteredBonds()
  const { data: summary } = useDashboard()
  const { toggleFilters, filtersOpen, tableDetailed, toggleTableDetailed } = useUiStore()
  const setFilter = useFilterStore((s) => s.set)
  const [params] = useSearchParams()

  // Deep-link support: /?q=TICKER seeds the quick filter (used by search palette).
  useEffect(() => {
    const q = params.get('q')
    if (q) setFilter('query', q)
  }, [params, setFilter])

  return (
    <div className="flex h-full flex-col gap-3 p-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Universe" value={summary?.bond_count ?? '—'} sub="bonds tracked" />
        <StatCard
          label="Cheap"
          value={summary?.cheap_count ?? '—'}
          accent="cheap"
          sub="RV z ≥ +0.75"
        />
        <StatCard
          label="Rich"
          value={summary?.rich_count ?? '—'}
          accent="rich"
          sub="RV z ≤ −0.75"
        />
        <StatCard label="Fair" value={summary?.fair_count ?? '—'} sub="within band" />
        <StatCard
          label="Avg Spread"
          value={summary ? `${num(summary.avg_spread_bps, 0)}bp` : '—'}
          accent="accent"
          sub="observed, universe"
        />
        <StatCard
          label="Stale Prints"
          value={summary?.stale_count ?? '—'}
          sub="no trade > 5d"
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={toggleFilters}
          className="rounded-md border border-terminal-border px-3 py-1.5 text-[11px] font-semibold tracking-wider text-terminal-dim uppercase transition-colors hover:border-terminal-dim hover:text-terminal-text"
        >
          {filtersOpen ? 'Hide' : 'Show'} filters <kbd className="num ml-1 text-[10px] text-terminal-faint">f</kbd>
        </button>
        <button
          onClick={toggleTableDetailed}
          className="rounded-md border border-terminal-border px-3 py-1.5 text-[11px] font-semibold tracking-wider text-terminal-dim uppercase transition-colors hover:border-terminal-dim hover:text-terminal-text"
        >
          {tableDetailed ? 'Essential columns' : 'All columns'}
        </button>
        <span className="text-xs text-terminal-faint">
          Click a row for full analytics · click headers to sort
        </span>
        <span className="ml-auto flex items-center gap-4 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-cheap" />
            <span className="text-terminal-dim">Cheap — trades wider than model fair value</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-rich" />
            <span className="text-terminal-dim">Rich — trades tighter</span>
          </span>
        </span>
      </div>

      <FilterBar shown={bonds.length} total={total} />

      <div className="min-h-0 flex-1">
        {isLoading ? (
          <div className="panel flex h-full items-center justify-center text-terminal-faint">
            Loading universe…
          </div>
        ) : (
          <BondTable bonds={bonds} />
        )}
      </div>
    </div>
  )
}
