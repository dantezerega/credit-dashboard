import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearch } from '../hooks/useApi'
import { useUiStore } from '../store/uiStore'
import { RvBadge } from './RvBadge'

export function SearchPalette() {
  const { searchOpen, setSearchOpen } = useUiStore()
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const { data: results } = useSearch(query)

  useEffect(() => {
    if (searchOpen) {
      setQuery('')
      setSelected(0)
      setTimeout(() => inputRef.current?.focus(), 30)
    }
  }, [searchOpen])

  useEffect(() => setSelected(0), [results])

  const choose = (index: number) => {
    const r = results?.[index]
    if (!r) return
    setSearchOpen(false)
    if (r.kind === 'bond' && r.cusip) {
      navigate(`/bond/${r.cusip}`)
    } else {
      navigate(`/?q=${encodeURIComponent(r.ticker)}`)
    }
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') setSearchOpen(false)
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelected((s) => Math.min(s + 1, (results?.length ?? 1) - 1))
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelected((s) => Math.max(s - 1, 0))
    }
    if (e.key === 'Enter') choose(selected)
  }

  return (
    <AnimatePresence>
      {searchOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[15vh]"
          onClick={() => setSearchOpen(false)}
        >
          <motion.div
            initial={{ scale: 0.97, y: -8 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.97, y: -8 }}
            transition={{ duration: 0.12 }}
            className="panel w-[640px] overflow-hidden shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Search CUSIP, ticker, issuer, bond…"
              className="w-full border-b border-terminal-border bg-transparent px-5 py-4 text-base placeholder-terminal-faint focus:outline-none"
            />
            <div className="max-h-[44vh] overflow-y-auto py-1">
              {(results ?? []).map((r, i) => (
                <button
                  key={`${r.kind}-${r.cusip ?? r.ticker}-${i}`}
                  onClick={() => choose(i)}
                  onMouseEnter={() => setSelected(i)}
                  className={`flex w-full items-center gap-4 px-5 py-2.5 text-left ${
                    i === selected ? 'bg-terminal-raised' : ''
                  }`}
                >
                  <span className="num w-12 text-[10px] tracking-[0.12em] text-terminal-faint uppercase">
                    {r.kind}
                  </span>
                  <span className="num w-18 text-terminal-accent">{r.ticker}</span>
                  <span className="flex-1 truncate text-sm text-terminal-text">
                    {r.kind === 'bond' ? r.description : r.issuer}
                  </span>
                  {r.cusip && <span className="num text-[11px] text-terminal-faint">{r.cusip}</span>}
                  {r.rv_label && <RvBadge label={r.rv_label} />}
                </button>
              ))}
              {query && results?.length === 0 && (
                <div className="px-5 py-10 text-center text-terminal-faint">
                  No matches. Try a ticker like PTVE or part of an issuer name.
                </div>
              )}
            </div>
            <div className="flex gap-5 border-t border-terminal-hairline px-5 py-2.5 text-[11px] text-terminal-faint">
              <span>↑↓ navigate</span>
              <span>↵ open</span>
              <span>esc close</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
