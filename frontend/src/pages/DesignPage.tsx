import { ANSWER_STATUS } from '../components/answerStatus'
import { CacheBadge, StatusBadge } from '../components/StatusBadge'
import { PageHeader, Skeleton } from '../components/PageHeader'
import type { AnswerStatus } from '../api/types'

// Development only (see App.tsx): a single page showing every token and shared component,
// so design changes can be checked in one place in both light and dark mode.

const SWATCHES = [
  ['bg', 'bg-bg'], ['surface', 'bg-surface'], ['raised', 'bg-raised'], ['hover', 'bg-hover'],
  ['accent', 'bg-accent'], ['ok', 'bg-ok'], ['warn', 'bg-warn'], ['caution', 'bg-caution'], ['danger', 'bg-danger'],
] as const

export function DesignPage() {
  return (
    <>
      <PageHeader title="Design system" description="Tokens and shared components. Visible in development only." />

      <section className="space-y-8">
        <div>
          <h2 className="mb-3 font-semibold">Colors</h2>
          <div className="flex flex-wrap gap-3">
            {SWATCHES.map(([name, cls]) => (
              <div key={name} className="w-24">
                <div className={`h-12 rounded-lg border border-line ${cls}`} />
                <p className="mt-1 font-mono text-xs text-fg-muted">{name}</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2 className="mb-3 font-semibold">Type</h2>
          <p className="text-2xl font-semibold tracking-tight">Page title, text-2xl semibold</p>
          <p className="mt-1">Body text, text-sm. Answers and passages render as plain text.</p>
          <p className="mt-1 text-fg-secondary">Secondary text for descriptions.</p>
          <p className="mt-1 text-xs text-fg-muted">Muted text for labels and hints.</p>
          <p className="mt-2 font-mono text-3xl">1,284 · 412 ms · $0.0031</p>
        </div>

        <div>
          <h2 className="mb-3 font-semibold">Answer status</h2>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(ANSWER_STATUS) as AnswerStatus[]).map((s) => (
              <StatusBadge key={s} status={s} />
            ))}
            <CacheBadge cache="exact" />
            <CacheBadge cache="semantic" />
          </div>
        </div>

        <div>
          <h2 className="mb-3 font-semibold">Buttons and citation chips</h2>
          <div className="flex flex-wrap items-center gap-2">
            <button className="rounded-lg bg-accent px-3 py-2 font-semibold text-white transition duration-150 hover:bg-accent-hover active:scale-[0.98]">Primary</button>
            <button className="rounded-lg border border-line-strong px-3 py-2 font-semibold transition duration-150 hover:bg-hover active:scale-[0.98]">Secondary</button>
            <button className="rounded-lg px-3 py-2 font-semibold text-danger transition duration-150 hover:bg-danger-soft">Delete</button>
            {[1, 2, 3].map((n) => (
              <button key={n} className="rounded-md bg-accent-soft px-2 py-0.5 font-mono text-xs font-medium text-accent-text transition duration-150 hover:bg-accent hover:text-white">
                {n}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2 className="mb-3 font-semibold">Loading</h2>
          <div className="max-w-md space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </div>
      </section>
    </>
  )
}
