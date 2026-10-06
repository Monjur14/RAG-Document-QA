import { ChatsCircleIcon, TrashIcon } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import type { Citation } from '../api/types'
import { useChat } from '../chat/chatStore'
import { ChatTurn } from '../chat/ChatTurn'
import { CitationPanel } from '../chat/CitationPanel'
import { Composer } from '../chat/Composer'

/**
 * Scrolls the least needed to show a turn between the sticky header and the sticky question box. When the turn is
 * taller than that space, its top (the question) wins: the end of a long answer can be scrolled to, a question that
 * vanished off the top cannot be read. Extra room above the turn comes from its CSS scroll-margin-top.
 * window.scrollBy rather than scrollIntoView, which can also scroll the page around an embedded preview.
 */
function reveal(el: HTMLElement) {
  const r = el.getBoundingClientRect()
  const top = (document.querySelector('header')?.getBoundingClientRect().bottom ?? 0) + (parseFloat(getComputedStyle(el).scrollMarginTop) || 0)
  const bottom = (document.querySelector('form[data-composer]')?.getBoundingClientRect().top ?? window.innerHeight) - 16
  let delta = r.bottom > bottom ? r.bottom - bottom : 0
  if (r.top - delta < top) delta = r.top - top
  if (Math.abs(delta) > 1) window.scrollBy({ top: delta, behavior: 'smooth' })
}

export function ChatPage() {
  const { turns, ask, retry, clear } = useChat()
  const [openCitation, setOpenCitation] = useState<Citation | null>(null)
  const busy = turns.some((t) => t.state === 'pending')

  // Follow the conversation when a question is sent and again when its answer arrives, keeping the question on
  // screen. Not on first render, so coming back to the page keeps its scroll position.
  const listRef = useRef<HTMLDivElement>(null)
  const last = turns.at(-1)
  const lastKey = last ? `${last.id}:${last.state}` : ''
  const seen = useRef(lastKey)
  useEffect(() => {
    const changed = lastKey !== '' && lastKey !== seen.current
    seen.current = lastKey
    const el = listRef.current?.lastElementChild
    if (!changed || !(el instanceof HTMLElement)) return
    const frame = requestAnimationFrame(() => reveal(el))
    return () => cancelAnimationFrame(frame)
  }, [lastKey])

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-10rem)] max-w-3xl flex-col">
      {turns.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center py-12 text-center">
          <ChatsCircleIcon size={32} className="text-fg-muted" aria-hidden="true" />
          <h1 className="mt-4 text-2xl font-semibold tracking-tight">Ask about your documents</h1>
          <p className="mt-2 max-w-md text-fg-secondary">
            Answers cite the passages they come from. When the documents do not support an answer, you get “I don't know” instead of a guess.
          </p>
        </div>
      ) : (
        <>
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-2xl font-semibold tracking-tight">Chat</h1>
            <button
              type="button"
              onClick={clear}
              disabled={busy}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-fg-secondary transition-colors duration-150 hover:bg-hover hover:text-fg disabled:opacity-40"
            >
              <TrashIcon size={14} aria-hidden="true" />
              Clear conversation
            </button>
          </div>
          <div ref={listRef} className="flex-1 space-y-8 pb-8" aria-live="polite">
            {turns.map((turn) => (
              <ChatTurn key={turn.id} turn={turn} onCite={setOpenCitation} onRetry={() => retry(turn.id)} />
            ))}
          </div>
        </>
      )}

      <Composer onAsk={ask} busy={busy} />
      <CitationPanel citation={openCitation} onClose={() => setOpenCitation(null)} />
    </div>
  )
}
