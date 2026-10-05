import type { ReactNode } from 'react'
import { Skeleton } from '../components/PageHeader'

/** One headline number. Numbers use the mono font so digits line up across tiles. */
export function StatTile({ label, value, sub, loading }: { label: string; value: ReactNode; sub?: ReactNode; loading?: boolean }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-xs text-fg-muted">{label}</p>
      {loading ? (
        <Skeleton className="mt-3 h-9 w-20" />
      ) : (
        <>
          <p className="mt-2 font-mono text-2xl tracking-tight">{value}</p>
          {sub && <p className="mt-1 text-xs text-fg-secondary">{sub}</p>}
        </>
      )}
    </div>
  )
}

export interface BarRow {
  key: string
  label: ReactNode
  value: number // drawn length
  display: string // text shown next to the bar
  title?: string // hover text with the exact numbers
}

/**
 * Horizontal bars, one hue, value printed beside every bar (so nothing depends on reading the length alone).
 * `max` fixes the scale, for example 1 for rates, so bars in different cards are comparable.
 */
export function BarList({ rows, max, label }: { rows: BarRow[]; max?: number; label: string }) {
  const top = max ?? Math.max(...rows.map((r) => r.value), 0)
  return (
    <ul className="space-y-3" aria-label={label}>
      {rows.map((r) => (
        <li key={r.key} title={r.title}>
          <div className="flex items-baseline justify-between gap-4 text-sm">
            <span className="min-w-0 truncate">{r.label}</span>
            <span className="shrink-0 font-mono text-xs text-fg-secondary">{r.display}</span>
          </div>
          <div className="mt-1 h-2 rounded-full bg-raised">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-300 ease-(--ease-fluid)"
              style={{ width: `${top > 0 ? Math.max((r.value / top) * 100, r.value > 0 ? 1 : 0) : 0}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function Card({ title, meta, children, className = '' }: { title: string; meta?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-4 ${className}`} aria-label={title}>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="font-semibold">{title}</h3>
        {meta && <p className="text-xs text-fg-muted">{meta}</p>}
      </div>
      {children}
    </section>
  )
}

export function Missing({ what, command }: { what: string; command: string }) {
  return (
    <p className="text-fg-secondary">
      No {what} results saved yet. Run <code className="rounded-md bg-raised px-1.5 py-0.5 font-mono text-xs">{command}</code> in{' '}
      <code className="rounded-md bg-raised px-1.5 py-0.5 font-mono text-xs">backend/</code>.
    </p>
  )
}
