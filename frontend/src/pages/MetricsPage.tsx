import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { EvalSection } from '../metrics/EvalSection'
import { RequestStats } from '../metrics/RequestStats'

const WINDOWS: { label: string; hours: number | null }[] = [
  { label: 'All time', hours: null },
  { label: 'Last 24 h', hours: 24 },
]

export function MetricsPage() {
  const [hours, setHours] = useState<number | null>(null)

  return (
    <>
      <PageHeader
        title="Metrics"
        description="Live request statistics, and the newest saved evaluation results. Read only."
        actions={
          <div role="group" aria-label="Time window" className="inline-flex rounded-lg border border-line bg-surface p-1">
            {WINDOWS.map((w) => (
              <button
                key={w.label}
                type="button"
                aria-pressed={hours === w.hours}
                onClick={() => setHours(w.hours)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors duration-150 ${hours === w.hours ? 'bg-raised text-fg' : 'text-fg-secondary hover:text-fg'}`}
              >
                {w.label}
              </button>
            ))}
          </div>
        }
      />

      <h2 className="sr-only">Requests</h2>
      <RequestStats hours={hours} />

      <h2 className="mt-12 mb-1 text-lg font-semibold tracking-tight">Evaluations</h2>
      <p className="mb-4 text-fg-secondary">
        From the newest result files in <span className="font-mono text-xs">backend/evals/results</span>. Run an eval script again to update them.
      </p>
      <EvalSection />

      <p className="mt-6 text-xs text-fg-muted">Costs are estimates from token counts and list prices. Local models cost $0.</p>
    </>
  )
}
