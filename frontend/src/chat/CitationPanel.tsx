import { FileTextIcon, XIcon } from '@phosphor-icons/react'
import { useEffect, useRef } from 'react'
import type { Citation } from '../api/types'

/**
 * Shows the full passage behind a citation. Built on <dialog>, so the browser handles focus trapping,
 * the Escape key and returning focus to the chip that opened it.
 * Slides in from the right on wide screens and up from the bottom on phones.
 * The passage comes from an uploaded document, so it is untrusted: rendered as plain text only.
 */
export function CitationPanel({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (citation && !dialog.open) dialog.showModal()
    if (!citation && dialog.open) dialog.close()
  }, [citation])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === e.currentTarget && onClose()} // a click on the backdrop closes it
      aria-labelledby="citation-title"
      className="fixed inset-x-0 top-auto bottom-0 m-0 max-h-[85dvh] w-full max-w-none rounded-t-xl border border-line bg-surface p-0 text-fg shadow-2xl backdrop:bg-black/40 open:animate-sheet-up sm:inset-y-0 sm:right-0 sm:left-auto sm:h-dvh sm:max-h-none sm:w-[28rem] sm:rounded-none sm:rounded-l-xl sm:open:animate-sheet-left"
    >
      {citation && (
        <div className="flex h-full flex-col">
          <header className="flex items-start gap-4 border-b border-line p-4">
            <span className="mt-0.5 rounded-md bg-accent-soft px-2 py-0.5 font-mono text-xs font-medium text-accent-text">{citation.index}</span>
            <div className="min-w-0 flex-1">
              <h2 id="citation-title" className="flex items-center gap-2 font-semibold">
                <FileTextIcon size={16} className="shrink-0 text-fg-muted" aria-hidden="true" />
                <span className="truncate" title={citation.source}>{citation.source}</span>
              </h2>
              <p className="mt-1 text-xs text-fg-secondary">
                {[citation.heading, citation.page != null ? `Page ${citation.page}` : null].filter(Boolean).join(' · ') || 'No heading'}
              </p>
            </div>
            <button
              type="button"
              autoFocus
              onClick={onClose}
              className="rounded-md p-1 text-fg-muted hover:bg-hover hover:text-fg"
              aria-label="Close passage"
            >
              <XIcon size={18} aria-hidden="true" />
            </button>
          </header>
          <div className="flex-1 overflow-y-auto p-4">
            <p className="text-xs font-medium text-fg-muted">Passage used in the answer</p>
            <p className="mt-2 leading-relaxed break-words whitespace-pre-wrap">{citation.text}</p>
          </div>
        </div>
      )}
    </dialog>
  )
}
