import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

interface Props {
  label: string
  value: ReactNode
  sub?: ReactNode
  accent?: 'cheap' | 'rich' | 'accent' | 'none'
}

const ACCENTS = {
  cheap: 'text-cheap',
  rich: 'text-rich',
  accent: 'text-terminal-accent',
  none: 'text-terminal-text',
}

export function StatCard({ label, value, sub, accent = 'none' }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="panel px-5 py-4"
    >
      <div className="text-[11px] font-semibold tracking-[0.14em] text-terminal-faint uppercase">
        {label}
      </div>
      <div className={`num mt-2 text-2xl leading-none font-medium ${ACCENTS[accent]}`}>{value}</div>
      {sub && <div className="mt-1.5 text-xs text-terminal-dim">{sub}</div>}
    </motion.div>
  )
}
