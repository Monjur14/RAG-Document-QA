import { ChatsCircleIcon, TrashIcon } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import type { Citation } from '../api/types'
import { useChat } from '../chat/chatStore'
import { ChatTurn } from '../chat/ChatTurn'
import { CitationPanel } from '../chat/CitationPanel'
import { Composer } from '../chat/Composer'

export function ChatPage() {
  const { turns, ask, retry, clear } = useChat()
  const [openCitation, setOpenCitation] = useState<Citation | null>(null)
  const busy = turns.some((t) => t.state === 'pending')

  // Follow the conversation when a question is added. window.scrollTo rather than scrollIntoView,
  // which can also scroll the page around an embedded preview.
  const count = useRef(turns.length)
  useEffect(() => {
    if (turns.length > count.current) window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
    count.current = turns.length
  }, [turns.length])

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
          <div className="flex-1 space-y-8 pb-8" aria-live="polite">
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
