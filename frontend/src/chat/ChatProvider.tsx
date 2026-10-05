import { useCallback, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { postJson } from '../api/client'
import type { AskRequest, AskResponse } from '../api/types'
import { expandFileTypes } from '../lib/fileTypes'
import { ChatContext } from './chatStore'
import type { AskFilters, Turn } from './chatStore'

function toRequest(question: string, f: AskFilters): AskRequest {
  return {
    question,
    // null means "no filter" to the backend; an empty list would match nothing.
    file_types: f.fileTypes.length ? expandFileTypes(f.fileTypes) : null,
    document_ids: f.documentIds.length ? f.documentIds : null,
  }
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const nextId = useRef(1)

  const run = useCallback(async (id: number, question: string, filters: AskFilters) => {
    const patch = (p: Partial<Turn>) => setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...p } : t)))
    try {
      patch({ response: await postJson<AskResponse>('/ask', toRequest(question, filters)), state: 'done' })
    } catch (error) {
      patch({ error, state: 'error' })
    }
  }, [])

  const ask = useCallback(
    (question: string, filters: AskFilters) => {
      const id = nextId.current++
      setTurns((prev) => [...prev, { id, question, filters, state: 'pending' }])
      void run(id, question, filters)
    },
    [run],
  )

  const retry = useCallback(
    (id: number) => {
      const turn = turns.find((t) => t.id === id)
      if (!turn) return
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, state: 'pending', error: undefined } : t)))
      void run(id, turn.question, turn.filters)
    },
    [run, turns],
  )

  const clear = useCallback(() => setTurns([]), [])
  const value = useMemo(() => ({ turns, ask, retry, clear }), [turns, ask, retry, clear])
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}
