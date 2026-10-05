import { ArrowClockwiseIcon, FunnelSimpleIcon, WarningCircleIcon } from '@phosphor-icons/react'
import type { AskResponse, Citation } from '../api/types'
import { Skeleton } from '../components/PageHeader'
import { CacheBadge, StatusBadge } from '../components/StatusBadge'
import { splitCitations } from '../lib/citations'
import { describeAskError } from '../lib/errors'
import { fileTypeLabels } from '../lib/fileTypes'
import type { Turn } from './chatStore'

const chip =
  'inline-flex items-center rounded-md bg-accent-soft px-1.5 py-px align-baseline font-mono text-xs font-medium text-accent-text transition-colors duration-150 hover:bg-accent hover:text-white'

/**
 * The answer as plain text, with [n] markers turned into buttons that open the passage.
 * A marker with no matching citation stays as plain text.
 */
function AnswerText({ response, onCite }: { response: AskResponse; onCite: (c: Citation) => void }) {
  const byIndex = new Map(response.citations.map((c) => [c.index, c]))
  return (
    <p className="leading-relaxed break-words whitespace-pre-wrap">
      {splitCitations(response.answer).map((seg, i) => {
        if (seg.kind === 'text') return seg.text
        const found = seg.indexes.map((n) => byIndex.get(n))
        if (found.some((c) => !c)) return seg.raw
        return (
          <span key={i} className="mx-0.5 inline-flex gap-0.5">
            {(found as Citation[]).map((c) => (
              <button key={c.index} type="button" onClick={() => onCite(c)} className={chip} aria-label={`Source ${c.index}: ${c.source}`}>
                {c.index}
              </button>
            ))}
          </span>
        )
      })}
    </p>
  )
}

function Meta({ response }: { response: AskResponse }) {
  const parts = [
    response.model,
    `${Math.round(response.latency_ms).toLocaleString()} ms`,
    response.confidence != null ? `confidence ${response.confidence.toFixed(2)}` : null,
  ].filter(Boolean)
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <StatusBadge status={response.status} />
      <CacheBadge cache={response.cache} />
      <span className="font-mono text-xs text-fg-muted">{parts.join(' · ')}</span>
    </div>
  )
}

function SourceList({ citations, onCite }: { citations: Citation[]; onCite: (c: Citation) => void }) {
  if (citations.length === 0) return null
  return (
    <div className="mt-4 border-t border-line pt-4">
      <p className="text-xs font-medium text-fg-muted">Sources</p>
      <ul className="mt-2 space-y-1">
        {citations.map((c) => (
          <li key={c.index}>
            <button
              type="button"
              onClick={() => onCite(c)}
              className="flex w-full items-baseline gap-2 rounded-md px-2 py-1 text-left transition-colors duration-150 hover:bg-hover"
            >
              <span className="font-mono text-xs text-accent-text">{c.index}</span>
              <span className="min-w-0 flex-1 truncate">
                {c.source}
                <span className="text-fg-muted">
                  {c.heading ? ` · ${c.heading}` : ''}
                  {c.page != null ? ` · p. ${c.page}` : ''}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function FilterNote({ turn }: { turn: Turn }) {
  const { fileTypes, documentIds } = turn.filters
  if (!fileTypes.length && !documentIds.length) return null
  const parts = [
    fileTypes.length ? fileTypeLabels(fileTypes).join(', ') : null,
    documentIds.length ? `${documentIds.length} ${documentIds.length === 1 ? 'document' : 'documents'}` : null,
  ].filter(Boolean)
  return (
    <p className="mt-1 flex items-center justify-end gap-1 text-xs text-fg-muted">
      <FunnelSimpleIcon size={12} aria-hidden="true" />
      Only {parts.join(' and ')}
    </p>
  )
}

export function ChatTurn({ turn, onCite, onRetry }: { turn: Turn; onCite: (c: Citation) => void; onRetry: () => void }) {
  return (
    <article className="space-y-3" aria-busy={turn.state === 'pending'}>
      <div className="flex flex-col items-end">
        <p className="max-w-[85%] rounded-xl bg-raised px-4 py-2 break-words whitespace-pre-wrap">{turn.question}</p>
        <FilterNote turn={turn} />
      </div>

      <div className="rounded-xl border border-line bg-surface p-4">
        {turn.state === 'pending' && (
          <div aria-label="Waiting for the answer" className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-11/12" />
            <Skeleton className="h-4 w-2/3" />
            <p className="pt-2 text-xs text-fg-muted">Searching your documents and writing an answer</p>
          </div>
        )}

        {turn.state === 'error' && <ErrorBody error={turn.error} onRetry={onRetry} />}

        {turn.state === 'done' && turn.response && (
          <>
            <AnswerText response={turn.response} onCite={onCite} />
            <Meta response={turn.response} />
            <SourceList citations={turn.response.citations} onCite={onCite} />
          </>
        )}
      </div>
    </article>
  )
}

function ErrorBody({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const { title, detail } = describeAskError(error)
  return (
    <div role="alert" className="flex items-start gap-2">
      <WarningCircleIcon size={18} weight="bold" className="mt-px shrink-0 text-danger" aria-hidden="true" />
      <div className="flex-1">
        <p className="font-medium">{title}</p>
        <p className="mt-1 text-fg-secondary">{detail}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-2 rounded-lg border border-line-strong px-3 py-1.5 text-xs font-semibold transition duration-150 hover:bg-hover active:scale-[0.98]"
        >
          <ArrowClockwiseIcon size={14} aria-hidden="true" />
          Try again
        </button>
      </div>
    </div>
  )
}
