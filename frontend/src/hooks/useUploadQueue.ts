import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { uploadDocument } from '../api/hooks'
import type { UploadResponse } from '../api/types'
import { validateFile } from '../lib/files'

export interface UploadItem {
  key: number
  name: string
  size: number
  state: 'waiting' | 'uploading' | 'done' | 'error'
  error?: string
  result?: UploadResponse
}

/**
 * Uploads files one at a time. Indexing is slow (parsing and embedding happen inside the request)
 * and the server rate limits uploads, so sending files in parallel would only make each one slower.
 */
export function useUploadQueue() {
  const queryClient = useQueryClient()
  const [items, setItems] = useState<UploadItem[]>([])
  const queue = useRef<{ key: number; file: File }[]>([])
  const inFlight = useRef(new Set<string>()) // name:size of files waiting or uploading
  const running = useRef(false)
  const nextKey = useRef(1)

  const update = useCallback((key: number, patch: Partial<UploadItem>) => {
    setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...patch } : item)))
  }, [])

  const drain = useCallback(async () => {
    if (running.current) return
    running.current = true
    while (queue.current.length > 0) {
      const { key, file } = queue.current.shift()!
      update(key, { state: 'uploading' })
      try {
        update(key, { state: 'done', result: await uploadDocument(file) })
      } catch (err) {
        update(key, { state: 'error', error: err instanceof ApiError ? err.message : 'Upload failed. Try again.' })
      } finally {
        inFlight.current.delete(`${file.name}:${file.size}`)
        // Refresh even after a failure: a file that fails during indexing still gets a "failed" row.
        void queryClient.invalidateQueries({ queryKey: ['documents'] })
      }
    }
    running.current = false
  }, [queryClient, update])

  const add = useCallback(
    (files: File[]) => {
      const added: UploadItem[] = []
      for (const file of files) {
        const id = `${file.name}:${file.size}`
        if (inFlight.current.has(id)) continue // the same file is already queued
        const key = nextKey.current++
        const problem = validateFile(file)
        if (problem) {
          added.push({ key, name: file.name, size: file.size, state: 'error', error: problem })
        } else {
          inFlight.current.add(id)
          queue.current.push({ key, file })
          added.push({ key, name: file.name, size: file.size, state: 'waiting' })
        }
      }
      setItems((prev) => [...added, ...prev])
      void drain()
    },
    [drain],
  )

  const dismiss = useCallback((key: number) => setItems((prev) => prev.filter((i) => i.key !== key)), [])
  const clearFinished = useCallback(
    () => setItems((prev) => prev.filter((i) => i.state === 'waiting' || i.state === 'uploading')),
    [],
  )

  return { items, add, dismiss, clearFinished }
}
