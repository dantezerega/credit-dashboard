export const bps = (decimal: number, digits = 0): string =>
  `${(decimal * 10_000).toFixed(digits)}`

export const pct = (decimal: number, digits = 2): string =>
  `${(decimal * 100).toFixed(digits)}%`

export const px = (price: number): string => price.toFixed(3)

export const num = (value: number, digits = 2): string => value.toFixed(digits)

export const money = (value: number): string => {
  const abs = Math.abs(value)
  if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `$${(value / 1e3).toFixed(0)}K`
  return `$${value.toFixed(0)}`
}

export const shortDate = (iso: string): string => {
  const d = new Date(iso + (iso.length === 10 ? 'T00:00:00' : ''))
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
}

export const maturityLabel = (iso: string): string => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: '2-digit' })
}

export const yearsToMaturity = (iso: string): number =>
  (new Date(iso + 'T00:00:00').getTime() - Date.now()) / (365.25 * 24 * 3600 * 1000)

export const rvColor = (label: string): string =>
  label === 'cheap' ? 'text-cheap' : label === 'rich' ? 'text-rich' : 'text-terminal-dim'

export const signColor = (value: number): string =>
  value > 0 ? 'text-cheap' : value < 0 ? 'text-rich' : 'text-terminal-dim'
