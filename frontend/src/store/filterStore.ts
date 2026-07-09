import { create } from 'zustand'
import type { RvLabel } from '../api/types'

export interface Filters {
  query: string
  sectors: string[]
  ratings: string[]
  rvLabels: RvLabel[]
  minDuration: number | null
  maxDuration: number | null
  minSpreadBps: number | null
  maxSpreadBps: number | null
  minYield: number | null
  maxYield: number | null
  minLiquidity: number | null
  maxPd: number | null
  minMaturity: number | null
  maxMaturity: number | null
}

const EMPTY: Filters = {
  query: '',
  sectors: [],
  ratings: [],
  rvLabels: [],
  minDuration: null,
  maxDuration: null,
  minSpreadBps: null,
  maxSpreadBps: null,
  minYield: null,
  maxYield: null,
  minLiquidity: null,
  maxPd: null,
  minMaturity: null,
  maxMaturity: null,
}

interface FilterState extends Filters {
  set: <K extends keyof Filters>(key: K, value: Filters[K]) => void
  toggleSector: (sector: string) => void
  toggleRating: (rating: string) => void
  toggleLabel: (label: RvLabel) => void
  reset: () => void
  activeCount: () => number
}

const toggle = <T,>(list: T[], item: T): T[] =>
  list.includes(item) ? list.filter((x) => x !== item) : [...list, item]

export const useFilterStore = create<FilterState>((set, get) => ({
  ...EMPTY,
  set: (key, value) => set({ [key]: value }),
  toggleSector: (sector) => set((s) => ({ sectors: toggle(s.sectors, sector) })),
  toggleRating: (rating) => set((s) => ({ ratings: toggle(s.ratings, rating) })),
  toggleLabel: (label) => set((s) => ({ rvLabels: toggle(s.rvLabels, label) })),
  reset: () => set(EMPTY),
  activeCount: () => {
    const s = get()
    let n = 0
    if (s.query) n++
    n += s.sectors.length + s.ratings.length + s.rvLabels.length
    for (const k of [
      'minDuration', 'maxDuration', 'minSpreadBps', 'maxSpreadBps', 'minYield',
      'maxYield', 'minLiquidity', 'maxPd', 'minMaturity', 'maxMaturity',
    ] as const) {
      if (s[k] !== null) n++
    }
    return n
  },
}))
