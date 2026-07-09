import { NavLink } from 'react-router-dom'
import { useDashboard } from '../hooks/useApi'
import { useUiStore } from '../store/uiStore'
import { shortDate } from '../utils/format'

const LINKS = [
  { to: '/', label: 'Monitor', key: 'd' },
  { to: '/analytics', label: 'Analytics', key: 'a' },
  { to: '/alerts', label: 'Alerts', key: 'l' },
]

export function TopBar() {
  const { setSearchOpen } = useUiStore()
  const { data: summary } = useDashboard()

  return (
    <header className="flex h-14 items-center gap-8 border-b border-terminal-border bg-terminal-panel/80 px-6 backdrop-blur">
      <div className="flex items-baseline gap-2.5">
        <span className="display text-lg font-bold text-terminal-accent">Credit RV</span>
        <span className="hidden text-[11px] font-medium tracking-[0.18em] text-terminal-faint uppercase sm:inline">
          Relative Value
        </span>
        <span className="hidden text-[11px] text-terminal-faint md:inline">· by Dante Zerega</span>
      </div>
      <nav className="flex h-full items-stretch gap-2">
        {LINKS.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === '/'}
            className={({ isActive }) =>
              `flex items-center border-b-2 px-4 text-xs font-semibold tracking-wider uppercase transition-colors ${
                isActive
                  ? 'border-terminal-accent text-terminal-text'
                  : 'border-transparent text-terminal-dim hover:text-terminal-text'
              }`
            }
          >
            {l.label}
            <span className="num ml-2 hidden text-[10px] text-terminal-faint lg:inline">g{l.key}</span>
          </NavLink>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-5">
        {summary && (
          <div className="num hidden items-center gap-4 text-xs md:flex">
            <span className="text-terminal-dim">
              As of <span className="text-terminal-text">{shortDate(summary.as_of_date)}</span>
            </span>
            <span className="text-cheap">{summary.cheap_count} cheap</span>
            <span className="text-rich">{summary.rich_count} rich</span>
            <span className="text-terminal-dim">{summary.bond_count} bonds</span>
          </div>
        )}
        <button
          onClick={() => setSearchOpen(true)}
          className="flex items-center gap-2.5 rounded-md border border-terminal-border px-3.5 py-1.5 text-xs text-terminal-dim transition-colors hover:border-terminal-dim hover:text-terminal-text"
        >
          Search
          <kbd className="num rounded bg-terminal-raised px-1.5 py-0.5 text-[10px]">⌘K</kbd>
        </button>
      </div>
    </header>
  )
}
