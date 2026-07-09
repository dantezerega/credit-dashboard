import { useMemo } from 'react'
import type { BondRow } from '../api/types'
import { useFilterStore } from '../store/filterStore'
import { yearsToMaturity } from '../utils/format'
import { useBonds } from './useApi'

/** Client-side screening over the full universe — instant filtering without
 * round-trips. The /api/screen endpoint provides the same logic server-side
 * for programmatic consumers. */
export function useFilteredBonds(): { bonds: BondRow[]; isLoading: boolean; total: number } {
  const { data, isLoading } = useBonds()
  const f = useFilterStore()

  const bonds = useMemo(() => {
    if (!data) return []
    const q = f.query.trim().toLowerCase()
    return data.filter((b) => {
      if (
        q &&
        !b.cusip.toLowerCase().includes(q) &&
        !b.ticker.toLowerCase().includes(q) &&
        !b.issuer.toLowerCase().includes(q)
      )
        return false
      if (f.sectors.length && !f.sectors.includes(b.sector)) return false
      if (f.ratings.length && !f.ratings.includes(b.rating)) return false
      if (f.rvLabels.length && !f.rvLabels.includes(b.rv_label)) return false
      if (f.minDuration !== null && b.duration < f.minDuration) return false
      if (f.maxDuration !== null && b.duration > f.maxDuration) return false
      const spreadBps = b.observed_spread * 10_000
      if (f.minSpreadBps !== null && spreadBps < f.minSpreadBps) return false
      if (f.maxSpreadBps !== null && spreadBps > f.maxSpreadBps) return false
      if (f.minYield !== null && b.ytm * 100 < f.minYield) return false
      if (f.maxYield !== null && b.ytm * 100 > f.maxYield) return false
      if (f.minLiquidity !== null && b.liquidity_score < f.minLiquidity) return false
      if (f.maxPd !== null && b.merton_pd * 100 > f.maxPd) return false
      const years = yearsToMaturity(b.maturity_date)
      if (f.minMaturity !== null && years < f.minMaturity) return false
      if (f.maxMaturity !== null && years > f.maxMaturity) return false
      return true
    })
  }, [data, f])

  return { bonds, isLoading, total: data?.length ?? 0 }
}
