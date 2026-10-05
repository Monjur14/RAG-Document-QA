import { createContext, useContext } from 'react'
import type { AskResponse } from '../api/types'

export interface AskFilters {
  fileTypes: string[] // keys from FILE_TYPE_GROUPS
  documentIds: number[]
}

export interface Turn {
  id: number
  question: string
  filters: AskFilters
  state: 'pending' | 'done' | 'error'
  response?: AskResponse
  error?: unknown
}

export interface ChatState {
  turns: Turn[]
  ask: (question: string, filters: AskFilters) => void
  retry: (id: number) => void
  clear: () => void
}

export const ChatContext = createContext<ChatState | null>(null)

/** The conversation lives above the routes, so it survives a trip to the Library page and back. */
export function useChat(): ChatState {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used inside <ChatProvider>')
  return ctx
}
