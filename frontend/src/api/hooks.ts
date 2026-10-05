import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { EvalResults } from './evals'
import type { DocumentInfo, Metrics, UploadResponse } from './types'

/** Polls /health so the top bar can show whether the backend is reachable. */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api<{ status: string }>('/health'),
    refetchInterval: 30_000,
    retry: false,
  })
}

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: () => api<DocumentInfo[]>('/documents'),
  })
}

export function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  // No Content-Type header: the browser sets multipart/form-data with the boundary itself.
  return api<UploadResponse>('/documents/upload', { method: 'POST', body: form })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/documents/${id}`, { method: 'DELETE' }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  })
}

/** Request statistics from the request log. `hours` limits them to a recent window; null means all time. */
export function useMetrics(hours: number | null) {
  return useQuery({
    queryKey: ['metrics', hours],
    queryFn: () => api<Metrics>(hours ? `/metrics?hours=${hours}` : '/metrics'),
  })
}

export function useEvalResults() {
  return useQuery({ queryKey: ['evals'], queryFn: () => api<EvalResults>('/evals/latest') })
}
