import { ArrowUpIcon, FunnelSimpleIcon } from '@phosphor-icons/react'
import { useId, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { useDocuments } from '../api/hooks'
import { MAX_QUESTION_CHARS } from '../api/types'
import { FILE_TYPE_GROUPS } from '../lib/fileTypes'
import type { AskFilters } from './chatStore'

const toggle = <T,>(list: T[], value: T) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value])

function Filters({ value, onChange }: { value: AskFilters; onChange: (f: AskFilters) => void }) {
  const { data: docs = [] } = useDocuments()
  const indexed = docs.filter((d) => d.status === 'indexed')
  const pill = (on: boolean) =>
    `rounded-md px-2 py-1 text-xs font-medium transition-colors duration-150 ${on ? 'bg-accent-soft text-accent-text ring-1 ring-accent/40 ring-inset' : 'bg-raised text-fg-secondary hover:text-fg'}`

  return (
    <div className="space-y-3 border-b border-line px-3 pt-2 pb-3">
      <fieldset>
        <legend className="text-xs font-medium text-fg-muted">File types</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {FILE_TYPE_GROUPS.map((g) => {
            const on = value.fileTypes.includes(g.key)
            return (
              <button key={g.key} type="button" aria-pressed={on} className={pill(on)} onClick={() => onChange({ ...value, fileTypes: toggle(value.fileTypes, g.key) })}>
                {g.label}
              </button>
            )
          })}
        </div>
      </fieldset>
      <fieldset>
        <legend className="text-xs font-medium text-fg-muted">Documents</legend>
        {indexed.length === 0 ? (
          <p className="mt-2 text-xs text-fg-muted">No indexed documents yet.</p>
        ) : (
          <div className="mt-2 flex max-h-32 flex-wrap gap-2 overflow-y-auto">
            {indexed.map((d) => {
              const on = value.documentIds.includes(d.id)
              return (
                <button key={d.id} type="button" aria-pressed={on} className={`${pill(on)} max-w-60 truncate`} title={d.filename} onClick={() => onChange({ ...value, documentIds: toggle(value.documentIds, d.id) })}>
                  {d.filename}
                </button>
              )
            })}
          </div>
        )}
      </fieldset>
      <p className="text-xs text-fg-muted">Nothing selected means every document is searched.</p>
    </div>
  )
}

export function Composer({ onAsk, busy }: { onAsk: (question: string, filters: AskFilters) => void; busy: boolean }) {
  const [question, setQuestion] = useState('')
  const [filters, setFilters] = useState<AskFilters>({ fileTypes: [], documentIds: [] })
  const [showFilters, setShowFilters] = useState(false)
  const filtersId = useId()
  const activeFilters = filters.fileTypes.length + filters.documentIds.length
  const canAsk = question.trim().length > 0 && !busy

  function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!canAsk) return
    onAsk(question.trim(), filters)
    setQuestion('')
  }

  // Enter sends, Shift+Enter adds a new line. Skipped while an input method is composing text.
  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form data-composer onSubmit={submit} className="sticky bottom-4 rounded-xl border border-line bg-surface shadow-lg shadow-black/5">
      {showFilters && (
        <div id={filtersId}>
          <Filters value={filters} onChange={setFilters} />
        </div>
      )}
      <div className="p-2">
        <label htmlFor="question" className="sr-only">Question</label>
        <textarea
          id="question"
          rows={2}
          maxLength={MAX_QUESTION_CHARS}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a question about your documents"
          className="block w-full resize-none rounded-lg bg-transparent px-3 py-2 text-base placeholder:text-fg-muted focus-visible:outline-none"
        />
        <div className="flex items-center gap-2 px-2 pb-1">
          <button
            type="button"
            aria-expanded={showFilters}
            aria-controls={filtersId}
            onClick={() => setShowFilters((s) => !s)}
            className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors duration-150 hover:bg-hover ${activeFilters ? 'text-accent-text' : 'text-fg-secondary'}`}
          >
            <FunnelSimpleIcon size={14} aria-hidden="true" />
            Filters{activeFilters ? ` (${activeFilters})` : ''}
          </button>
          <span className={`ml-auto font-mono text-xs ${MAX_QUESTION_CHARS - question.length < 50 ? 'text-caution' : 'text-fg-muted'}`}>
            {question.length}/{MAX_QUESTION_CHARS}
          </span>
          <button
            type="submit"
            disabled={!canAsk}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white transition duration-150 hover:bg-accent-hover active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? 'Answering' : 'Ask'}
            <ArrowUpIcon size={16} weight="bold" aria-hidden="true" />
          </button>
        </div>
      </div>
    </form>
  )
}
