import { CheckCircleIcon, ShieldWarningIcon, WarningCircleIcon, XIcon } from '@phosphor-icons/react'
import type { UploadItem } from '../hooks/useUploadQueue'
import { formatBytes, scannerNotes } from '../lib/files'

function Progress() {
  // Indexing happens inside one request, so there is no real percentage to show. This bar only says "working".
  return (
    <div className="mt-2 h-1 overflow-hidden rounded-full bg-raised" aria-hidden="true">
      <div className="h-full w-1/3 animate-indeterminate rounded-full bg-accent" />
    </div>
  )
}

function ItemStatus({ item }: { item: UploadItem }) {
  switch (item.state) {
    case 'waiting':
      return <p className="text-xs text-fg-muted">Waiting</p>
    case 'uploading':
      return (
        <>
          <p className="text-xs text-fg-secondary">Uploading and indexing. Large files can take a minute.</p>
          <Progress />
        </>
      )
    case 'error':
      return (
        <p className="flex items-start gap-1 text-xs text-danger">
          <WarningCircleIcon size={14} weight="bold" className="mt-0.5 shrink-0" aria-hidden="true" />
          {item.error}
        </p>
      )
    case 'done': {
      const r = item.result!
      const notes = scannerNotes(r)
      return (
        <>
          <p className="flex items-center gap-1 text-xs text-ok">
            <CheckCircleIcon size={14} weight="bold" aria-hidden="true" />
            Indexed into {r.chunks} {r.chunks === 1 ? 'chunk' : 'chunks'}
          </p>
          {notes.map((note) => (
            <p key={note} className="mt-1 flex items-center gap-1 text-xs text-caution">
              <ShieldWarningIcon size={14} weight="bold" aria-hidden="true" />
              {note}
            </p>
          ))}
        </>
      )
    }
  }
}

export function UploadList({ items, onDismiss, onClear }: { items: UploadItem[]; onDismiss: (key: number) => void; onClear: () => void }) {
  if (items.length === 0) return null
  const anyFinished = items.some((i) => i.state === 'done' || i.state === 'error')

  return (
    <section aria-label="Uploads" className="mt-4 rounded-xl border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-4 py-2">
        <h2 className="text-xs font-medium text-fg-muted">Uploads</h2>
        {anyFinished && (
          <button type="button" onClick={onClear} className="rounded-md px-2 py-1 text-xs font-medium text-fg-secondary hover:bg-hover hover:text-fg">
            Clear finished
          </button>
        )}
      </div>
      <ul className="divide-y divide-line" aria-live="polite">
        {items.map((item) => (
          <li key={item.key} className="flex items-start gap-4 px-4 py-3">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium" title={item.name}>
                {item.name} <span className="font-mono text-xs font-normal text-fg-muted">{formatBytes(item.size)}</span>
              </p>
              <div className="mt-1">
                <ItemStatus item={item} />
              </div>
            </div>
            {(item.state === 'done' || item.state === 'error') && (
              <button
                type="button"
                onClick={() => onDismiss(item.key)}
                className="rounded-md p-1 text-fg-muted hover:bg-hover hover:text-fg"
                aria-label={`Dismiss ${item.name}`}
              >
                <XIcon size={16} aria-hidden="true" />
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
