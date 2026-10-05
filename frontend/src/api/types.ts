// Mirrors the Pydantic models in backend/app/models.py. Keep the two in sync.

export interface DocumentInfo {
  id: number
  filename: string
  file_type: string
  status: string // "pending" | "indexed" | "failed"
  error: string | null
  created_at: string // ISO timestamp
  chunk_count: number
  quarantined: number // chunks held back from search by the scanner
  sanitized: number // chunks kept after an injected paragraph was cut out
  flags: string[]
}

export interface ParsedSection {
  text: string
  page: number | null
  heading: string | null
  source: string
}

export interface UploadResponse {
  document_id: number
  filename: string
  file_type: string
  status: string
  sections: number
  chunks: number
  characters: number
  preview: ParsedSection[]
  quarantined: number
  sanitized: number
  flags: string[]
}

export type RetrievalMode = 'vector' | 'keyword' | 'hybrid'

export interface AskRequest {
  question: string
  k?: number
  mode?: RetrievalMode
  file_types?: string[] | null
  document_ids?: number[] | null
}

export type AnswerStatus = 'answered' | 'insufficient_evidence' | 'model_declined' | 'uncited' | 'blocked'
export type CacheStatus = 'miss' | 'exact' | 'semantic'

export interface Citation {
  index: number
  chunk_id: number
  document_id: number
  source: string
  heading: string | null
  page: number | null
  text: string
}

export interface AskResponse {
  question: string
  answer: string
  status: AnswerStatus
  citations: Citation[]
  confidence: number | null
  model: string | null
  prompt_tokens: number | null
  completion_tokens: number | null
  latency_ms: number
  retrieved: number
  cache: CacheStatus
  flags: string[]
}

export interface Metrics {
  requests: number
  error_rate: number
  cache_hit_rate: number
  total_cost_usd: number
  avg_cost_usd: number
  prompt_tokens: number
  completion_tokens: number
  latency_ms: { p50: number; p95: number }
  llm_latency_ms: { p50: number; p95: number }
  by_status: Record<string, number>
  by_model: Record<string, number>
}

// Limits that match the server. The server still enforces them; these only give faster feedback.
export const MAX_QUESTION_CHARS = 500
export const MAX_UPLOAD_MB = 20
export const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.html', '.htm', '.md', '.markdown', '.txt']
