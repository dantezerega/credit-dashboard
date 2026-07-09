import { useCallback, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { BondRow } from '../api/types'
import { useUiStore } from '../store/uiStore'
import { bps, maturityLabel, num, pct, px, rvColor, signColor } from '../utils/format'
import { RvBadge } from './RvBadge'

type SortDir = 'asc' | 'desc'

interface Column {
  key: string
  label: string
  group: string
  width: number
  align?: 'left' | 'right'
  essential?: boolean
  value: (b: BondRow) => string | number
  render: (b: BondRow) => React.ReactNode
}

const COLUMNS: Column[] = [
  { key: 'issuer', label: 'Issuer', group: 'Bond', width: 190, align: 'left', essential: true, value: (b) => b.issuer,
    render: (b) => <span className="truncate font-medium text-terminal-text">{b.issuer}</span> },
  { key: 'ticker', label: 'Ticker', group: 'Bond', width: 70, align: 'left', essential: true, value: (b) => b.ticker,
    render: (b) => <span className="num text-terminal-accent">{b.ticker}</span> },
  { key: 'cusip', label: 'CUSIP', group: 'Bond', width: 100, align: 'left', value: (b) => b.cusip,
    render: (b) => <span className="num text-terminal-dim">{b.cusip}</span> },
  { key: 'rating', label: 'Rtg', group: 'Bond', width: 58, align: 'left', essential: true, value: (b) => b.rating,
    render: (b) => <span className="num">{b.rating}</span> },
  { key: 'coupon', label: 'Cpn %', group: 'Bond', width: 68, essential: true, value: (b) => b.coupon,
    render: (b) => <span className="num text-terminal-dim">{(b.coupon * 100).toFixed(3)}</span> },
  { key: 'maturity_date', label: 'Maturity', group: 'Bond', width: 86, essential: true, value: (b) => b.maturity_date,
    render: (b) => <span className="num text-terminal-dim">{maturityLabel(b.maturity_date)}</span> },
  { key: 'duration', label: 'Dur', group: 'Bond', width: 56, essential: true, value: (b) => b.duration,
    render: (b) => <span className="num text-terminal-dim">{num(b.duration, 1)}</span> },

  { key: 'price', label: 'Px', group: 'Pricing', width: 76, essential: true, value: (b) => b.price,
    render: (b) => <span className="num">{px(b.price)}</span> },
  { key: 'ytm', label: 'Yld %', group: 'Pricing', width: 68, essential: true, value: (b) => b.ytm,
    render: (b) => <span className="num">{(b.ytm * 100).toFixed(2)}</span> },
  { key: 'g_spread', label: 'G bp', group: 'Pricing', width: 62, value: (b) => b.g_spread,
    render: (b) => <span className="num text-terminal-dim">{bps(b.g_spread)}</span> },
  { key: 'z_spread', label: 'Z bp', group: 'Pricing', width: 64, essential: true, value: (b) => b.z_spread,
    render: (b) => <span className="num">{bps(b.z_spread)}</span> },
  { key: 'oas', label: 'OAS bp', group: 'Pricing', width: 68, value: (b) => b.oas,
    render: (b) => <span className="num text-terminal-dim">{bps(b.oas)}</span> },

  { key: 'liquidity_score', label: 'Liq', group: 'Liquidity', width: 58, essential: true, value: (b) => b.liquidity_score,
    render: (b) => (
      <span className={`num ${b.liquidity_score < 30 ? 'text-rich' : b.liquidity_score > 70 ? 'text-cheap' : 'text-terminal-dim'}`}>
        {num(b.liquidity_score, 0)}
      </span>
    ) },

  { key: 'merton_pd', label: 'PD %', group: 'Credit risk', width: 70, essential: true, value: (b) => b.merton_pd,
    render: (b) => <span className="num">{(b.merton_pd * 100).toFixed(2)}</span> },
  { key: 'market_implied_pd', label: 'Mkt PD %', group: 'Credit risk', width: 82, value: (b) => b.market_implied_pd,
    render: (b) => <span className="num text-terminal-dim">{(b.market_implied_pd * 100).toFixed(2)}</span> },

  { key: 'fair_spread', label: 'Fair bp', group: 'Relative value', width: 68, essential: true, value: (b) => b.fair_spread,
    render: (b) => <span className="num text-terminal-dim">{bps(b.fair_spread)}</span> },
  { key: 'observed_spread', label: 'Obs bp', group: 'Relative value', width: 68, value: (b) => b.observed_spread,
    render: (b) => <span className="num text-terminal-dim">{bps(b.observed_spread)}</span> },
  { key: 'residual', label: 'Misprc bp', group: 'Relative value', width: 82, essential: true, value: (b) => b.residual,
    render: (b) => (
      <span className={`num font-semibold ${signColor(b.residual)}`}>
        {b.residual > 0 ? '+' : ''}
        {bps(b.residual)}
      </span>
    ) },
  { key: 'rv_score', label: 'RV z', group: 'Relative value', width: 64, essential: true, value: (b) => b.rv_score,
    render: (b) => <span className={`num font-semibold ${rvColor(b.rv_label)}`}>{num(b.rv_score, 2)}</span> },
  { key: 'rv_label', label: 'Signal', group: 'Relative value', width: 92, align: 'left', essential: true, value: (b) => b.rv_label,
    render: (b) => <RvBadge label={b.rv_label} /> },
]

const RAIL: Record<string, string> = {
  cheap: 'border-l-cheap',
  rich: 'border-l-rich',
  fair: 'border-l-transparent',
}

export function BondTable({ bonds }: { bonds: BondRow[] }) {
  const navigate = useNavigate()
  const { tableDetailed } = useUiStore()
  const [sortKey, setSortKey] = useState('rv_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [widths, setWidths] = useState<Record<string, number>>({})
  const dragState = useRef<{ key: string; startX: number; startWidth: number } | null>(null)

  const columns = useMemo(
    () => (tableDetailed ? COLUMNS : COLUMNS.filter((c) => c.essential)),
    [tableDetailed],
  )

  // Header band: contiguous runs of the same group, with span = visible cols.
  const groups = useMemo(() => {
    const out: { name: string; span: number }[] = []
    for (const col of columns) {
      const last = out[out.length - 1]
      if (last && last.name === col.group) last.span++
      else out.push({ name: col.group, span: 1 })
    }
    return out
  }, [columns])

  const groupStartKeys = useMemo(() => {
    const keys = new Set<string>()
    let prev = ''
    for (const col of columns) {
      if (col.group !== prev) keys.add(col.key)
      prev = col.group
    }
    return keys
  }, [columns])

  const sorted = useMemo(() => {
    const col = COLUMNS.find((c) => c.key === sortKey) ?? COLUMNS[0]
    const dir = sortDir === 'asc' ? 1 : -1
    return [...bonds].sort((a, b) => {
      const va = col.value(a)
      const vb = col.value(b)
      if (va < vb) return -dir
      if (va > vb) return dir
      return 0
    })
  }, [bonds, sortKey, sortDir])

  const onSort = (key: string) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const startResize = useCallback((e: React.MouseEvent, key: string, currentWidth: number) => {
    e.preventDefault()
    e.stopPropagation()
    dragState.current = { key, startX: e.clientX, startWidth: currentWidth }
    const onMove = (ev: MouseEvent) => {
      if (!dragState.current) return
      const delta = ev.clientX - dragState.current.startX
      const next = Math.max(44, dragState.current.startWidth + delta)
      setWidths((w) => ({ ...w, [dragState.current!.key]: next }))
    }
    const onUp = () => {
      dragState.current = null
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [])

  const divider = (key: string) => (groupStartKeys.has(key) && key !== columns[0].key ? 'border-l border-l-terminal-border' : '')

  return (
    <div className="panel h-full overflow-auto">
      <table className="w-max min-w-full border-collapse text-[12.5px]">
        <thead className="sticky top-0 z-10">
          <tr className="bg-terminal-raised">
            {groups.map((g, i) => (
              <th
                key={`${g.name}-${i}`}
                colSpan={g.span}
                className={`px-3 pt-2.5 pb-1 text-left text-[10px] font-semibold tracking-[0.16em] whitespace-nowrap uppercase ${
                  g.name === 'Relative value' ? 'text-terminal-accent' : 'text-terminal-faint'
                } ${i > 0 ? 'border-l border-l-terminal-border' : ''} ${i === 0 ? 'border-l-[3px] border-l-transparent' : ''}`}
              >
                {g.name}
              </th>
            ))}
          </tr>
          <tr className="bg-terminal-raised">
            {columns.map((col, i) => {
              const w = widths[col.key] ?? col.width
              const active = sortKey === col.key
              return (
                <th
                  key={col.key}
                  style={{ width: w, minWidth: w, maxWidth: w }}
                  onClick={() => onSort(col.key)}
                  className={`relative cursor-pointer border-b border-terminal-border px-3 pt-1 pb-2.5 text-[11px] font-semibold tracking-[0.08em] whitespace-nowrap uppercase select-none ${
                    active ? 'text-terminal-accent' : 'text-terminal-dim'
                  } ${col.align === 'left' ? 'text-left' : 'text-right'} ${i === 0 ? 'border-l-[3px] border-l-transparent' : divider(col.key)} hover:text-terminal-text`}
                >
                  {col.label}
                  {active && <span className="ml-1 text-[9px]">{sortDir === 'asc' ? '▲' : '▼'}</span>}
                  <span
                    onMouseDown={(e) => startResize(e, col.key, w)}
                    onClick={(e) => e.stopPropagation()}
                    className="absolute top-0 right-0 h-full w-1.5 cursor-col-resize hover:bg-terminal-accent/40"
                  />
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((b) => (
            <tr
              key={b.cusip}
              onClick={() => navigate(`/bond/${b.cusip}`)}
              className="cursor-pointer border-b border-terminal-hairline transition-colors hover:bg-terminal-raised/60"
            >
              {columns.map((col, i) => {
                const w = widths[col.key] ?? col.width
                return (
                  <td
                    key={col.key}
                    style={{ width: w, minWidth: w, maxWidth: w }}
                    className={`overflow-hidden px-3 py-2.5 whitespace-nowrap ${
                      col.align === 'left' ? 'text-left' : 'text-right'
                    } ${i === 0 ? `border-l-[3px] ${RAIL[b.rv_label]}` : divider(col.key)}`}
                  >
                    {col.render(b)}
                  </td>
                )
              })}
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-6 py-16 text-center text-terminal-faint">
                No bonds match the current filters. Clear a filter to widen the universe.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
