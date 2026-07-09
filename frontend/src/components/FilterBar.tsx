import { AnimatePresence, motion } from 'framer-motion'
import type { RvLabel } from '../api/types'
import { useBonds } from '../hooks/useApi'
import { useFilterStore, type Filters } from '../store/filterStore'
import { useUiStore } from '../store/uiStore'

const RATINGS = ['AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-', 'BB+', 'BB', 'BB-', 'B+', 'B', 'B-', 'CCC+', 'CCC']
const LABELS: RvLabel[] = ['cheap', 'fair', 'rich']

const INPUT =
  'num rounded-md border border-terminal-border bg-terminal-bg px-2.5 py-1.5 text-xs placeholder-terminal-faint focus:border-terminal-accent focus:outline-none'

function Chip({ active, onClick, children, tone }: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
  tone?: string
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-wide transition-colors ${
        active
          ? (tone ?? 'border-terminal-accent bg-terminal-accent/15 text-terminal-accent')
          : 'border-terminal-border text-terminal-dim hover:border-terminal-dim hover:text-terminal-text'
      }`}
    >
      {children}
    </button>
  )
}

function RangeInput({ label, minKey, maxKey, step = 1 }: {
  label: string
  minKey: keyof Filters
  maxKey: keyof Filters
  step?: number
}) {
  const store = useFilterStore()
  const parse = (v: string) => (v === '' ? null : Number(v))
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-16 text-[10px] font-semibold tracking-[0.1em] text-terminal-faint uppercase">{label}</span>
      <input
        type="number"
        step={step}
        placeholder="min"
        value={(store[minKey] as number | null) ?? ''}
        onChange={(e) => store.set(minKey, parse(e.target.value) as never)}
        className={`${INPUT} w-[70px]`}
      />
      <span className="text-terminal-faint">–</span>
      <input
        type="number"
        step={step}
        placeholder="max"
        value={(store[maxKey] as number | null) ?? ''}
        onChange={(e) => store.set(maxKey, parse(e.target.value) as never)}
        className={`${INPUT} w-[70px]`}
      />
    </div>
  )
}

export function FilterBar({ shown, total }: { shown: number; total: number }) {
  const store = useFilterStore()
  const { filtersOpen } = useUiStore()
  const { data: bonds } = useBonds()
  const sectors = [...new Set((bonds ?? []).map((b) => b.sector))].sort()
  const usedRatings = new Set((bonds ?? []).map((b) => b.rating))

  return (
    <AnimatePresence initial={false}>
      {filtersOpen && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="overflow-hidden"
        >
          <div className="panel mb-3 space-y-3.5 p-5">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <input
                value={store.query}
                onChange={(e) => store.set('query', e.target.value)}
                placeholder="Filter issuer, ticker, or CUSIP…"
                className="w-64 rounded-md border border-terminal-border bg-terminal-bg px-3 py-1.5 text-xs placeholder-terminal-faint focus:border-terminal-accent focus:outline-none"
              />
              <div className="flex items-center gap-1.5">
                {LABELS.map((l) => (
                  <Chip
                    key={l}
                    active={store.rvLabels.includes(l)}
                    onClick={() => store.toggleLabel(l)}
                    tone={
                      l === 'cheap'
                        ? 'border-cheap bg-cheap/15 text-cheap'
                        : l === 'rich'
                          ? 'border-rich bg-rich/15 text-rich'
                          : undefined
                    }
                  >
                    {l.toUpperCase()}
                  </Chip>
                ))}
              </div>
              <RangeInput label="Duration" minKey="minDuration" maxKey="maxDuration" step={0.5} />
              <RangeInput label="Sprd bps" minKey="minSpreadBps" maxKey="maxSpreadBps" step={10} />
              <RangeInput label="Yield %" minKey="minYield" maxKey="maxYield" step={0.25} />
              <RangeInput label="Mty yrs" minKey="minMaturity" maxKey="maxMaturity" step={1} />
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-semibold tracking-[0.1em] text-terminal-faint uppercase">Liq ≥</span>
                <input
                  type="number"
                  value={store.minLiquidity ?? ''}
                  onChange={(e) => store.set('minLiquidity', e.target.value === '' ? null : Number(e.target.value))}
                  className={`${INPUT} w-16`}
                />
                <span className="ml-3 text-[10px] font-semibold tracking-[0.1em] text-terminal-faint uppercase">PD ≤ %</span>
                <input
                  type="number"
                  step={0.5}
                  value={store.maxPd ?? ''}
                  onChange={(e) => store.set('maxPd', e.target.value === '' ? null : Number(e.target.value))}
                  className={`${INPUT} w-16`}
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-2 text-[10px] font-semibold tracking-[0.1em] text-terminal-faint uppercase">Sector</span>
              {sectors.map((s) => (
                <Chip key={s} active={store.sectors.includes(s)} onClick={() => store.toggleSector(s)}>
                  {s}
                </Chip>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-2 text-[10px] font-semibold tracking-[0.1em] text-terminal-faint uppercase">Rating</span>
              {RATINGS.filter((r) => usedRatings.has(r)).map((r) => (
                <Chip key={r} active={store.ratings.includes(r)} onClick={() => store.toggleRating(r)}>
                  {r}
                </Chip>
              ))}
              <div className="ml-auto flex items-center gap-4">
                <span className="num text-xs text-terminal-dim">
                  {shown} / {total} bonds
                </span>
                {store.activeCount() > 0 && (
                  <button
                    onClick={store.reset}
                    className="text-[11px] font-semibold tracking-wider text-terminal-accent uppercase hover:underline"
                  >
                    Clear ({store.activeCount()})
                  </button>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
