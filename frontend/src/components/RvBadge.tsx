import type { RvLabel } from '../api/types'

const STYLES: Record<RvLabel, string> = {
  cheap: 'bg-cheap/12 text-cheap border-cheap/35',
  rich: 'bg-rich/12 text-rich border-rich/35',
  fair: 'bg-terminal-raised/80 text-terminal-dim border-terminal-border',
}

export function RvBadge({ label }: { label: RvLabel }) {
  return (
    <span
      className={`inline-block min-w-[60px] rounded-full border px-2.5 py-0.5 text-center text-[10px] font-semibold tracking-[0.12em] uppercase ${STYLES[label]}`}
    >
      {label}
    </span>
  )
}
