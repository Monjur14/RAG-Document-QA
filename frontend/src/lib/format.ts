// Number formatting for the metrics page. Rates arrive as 0..1 fractions.

export const pct = (x: number | null | undefined, digits = 1) =>
  x == null || Number.isNaN(x) ? '–' : `${(x * 100).toFixed(digits).replace(/\.0+$/, '')}%`

export const ms = (x: number | null | undefined) => (x == null ? '–' : `${Math.round(x).toLocaleString()} ms`)

/** Small costs need more decimals: $0.0031 rather than $0.00. */
export function usd(x: number | null | undefined) {
  if (x == null) return '–'
  if (x === 0) return '$0'
  return x < 0.01 ? `$${x.toFixed(4)}` : `$${x.toFixed(2)}`
}

export function shortDate(iso: string | undefined) {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
