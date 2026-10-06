import { ArrowClockwiseIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { useMetrics } from '../api/hooks'
import type { AnswerStatus } from '../api/types'
import { ANSWER_STATUS } from '../components/answerStatus'
import { Skeleton } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'
import { ms, pct, usd } from '../lib/format'
import { BarList, Card, StatTile } from './parts'

const isAnswerStatus = (s: string): s is AnswerStatus => s in ANSWER_STATUS

function StatusLabel({ status }: { status: string }) {
  if (isAnswerStatus(status))
    return (
      <span className="inline-flex items-center gap-2">
        <StatusBadge status={status} label={ANSWER_STATUS[status].metricLabel} />
        <span className="text-xs text-fg-muted">{ANSWER_STATUS[status].reason}</span>
      </span>
    )
  if (status === 'error')
    return (
      <span className="inline-flex items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-md bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger">
          <WarningCircleIcon size={14} weight="bold" aria-hidden="true" />
          Error
        </span>
        <span className="text-xs text-fg-muted">model or server failure, no answer</span>
      </span>
    )
  return <span className="text-xs">{status}</span>
}

export function RequestStats({ hours }: { hours: number | null }) {
  const { data: m, isPending, isError, error, refetch, isFetching } = useMetrics(hours)

  if (isError)
    return (
      <div role="alert" className="rounded-xl border border-line bg-surface p-6 text-center">
        <p className="font-medium">Could not load request statistics</p>
        <p className="mt-1 text-fg-secondary">{error.message}</p>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-line-strong px-3 py-2 font-semibold transition duration-150 hover:bg-hover active:scale-[0.98] disabled:opacity-50"
        >
          <ArrowClockwiseIcon size={16} aria-hidden="true" />
          Try again
        </button>
      </div>
    )

  const n = m?.requests ?? 0
  const share = (count: number) => (n ? count / n : 0)
  const sorted = (rec: Record<string, number>) => Object.entries(rec).sort((a, b) => b[1] - a[1])

  return (
    <>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        <StatTile loading={isPending} label="Requests" value={n.toLocaleString()} />
        <StatTile loading={isPending} label="Error rate" value={pct(m?.error_rate)} sub="model or server failures" />
        <StatTile loading={isPending} label="Cache hit rate" value={pct(m?.cache_hit_rate)} sub="exact and similar" />
        <StatTile loading={isPending} label="Estimated cost" value={usd(m?.total_cost_usd)} sub={`${usd(m?.avg_cost_usd)} per request`} />
        <StatTile loading={isPending} label="p50 latency" value={ms(m?.latency_ms?.p50)} sub={`model only ${ms(m?.llm_latency_ms?.p50)}`} />
        <StatTile loading={isPending} label="p95 latency" value={ms(m?.latency_ms?.p95)} sub={`model only ${ms(m?.llm_latency_ms?.p95)}`} />
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card title="By status">
          {isPending ? (
            <Skeleton className="h-16 w-full" />
          ) : n === 0 ? (
            <p className="text-fg-secondary">No questions asked {hours ? 'in this period' : 'yet'}.</p>
          ) : (
            <BarList
              label="Requests by status"
              max={1}
              rows={sorted(m?.by_status ?? {}).map(([status, count]) => ({
                key: status,
                label: <StatusLabel status={status} />,
                value: share(count),
                display: `${count} · ${pct(share(count), 0)}`,
              }))}
            />
          )}
        </Card>
        <Card title="By model" meta="which model wrote the answer; shows when fallback was used">
          {isPending ? (
            <Skeleton className="h-16 w-full" />
          ) : Object.keys(m?.by_model ?? {}).length === 0 ? (
            <p className="text-fg-secondary">No model calls {hours ? 'in this period' : 'yet'}.</p>
          ) : (
            <BarList
              label="Requests by model"
              max={1}
              rows={sorted(m?.by_model ?? {}).map(([model, count]) => ({
                key: model,
                label: <span className="font-mono text-xs">{model}</span>,
                value: share(count),
                display: `${count} · ${pct(share(count), 0)}`,
              }))}
            />
          )}
        </Card>
      </div>
    </>
  )
}
