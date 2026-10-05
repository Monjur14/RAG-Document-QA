// Shape of GET /evals/latest (backend/app/eval_results.py). Only the fields the metrics page reads are typed;
// every eval kind can be null when no result file exists yet, and older files may lack newer fields.

export interface RetrievalMode {
  'hit@1': number
  'hit@3': number
  'hit@5': number
  mrr: number
  avg_ms_per_query: number
  by_format?: Record<string, { 'hit@1': number; 'hit@5': number; mrr: number; n: number }>
}

export interface RetrievalEval {
  file: string
  timestamp: string
  questions: number
  k: number
  chunking?: { strategy: string; chunk_size: number; overlap: number }
  modes: Record<string, RetrievalMode>
}

export interface AnswersEval {
  file: string
  timestamp: string
  answer_model?: string
  answerable: {
    n: number
    answered: number
    success: number
    citation_supports_given_answered?: number
    context_had_answer?: number
    p50_ms?: number
    p95_ms?: number
    by_format?: Record<string, { n: number; success: number; answered: number }>
  }
  unanswerable?: { n: number; refused: number; leaked_or_obeyed: number }
}

export interface CacheEval {
  file: string
  timestamp: string
  threshold: number
  workload: { questions: number; requests: number }
  cache_on: { requests: number; llm_calls: number; exact_hits: number; semantic_hits: number }
  savings: { latency_avg: number; cost: number; llm_calls: number; prompt_tokens: number }
  wrong_hits_on_near_misses?: unknown[]
}

export interface RedteamRun {
  file: string
  timestamp: string
  label: string
  cases: number
  attack_success_rate: number
  legit_answer_preserved_on_poisoned_docs?: number
}

export interface EvalResults {
  retrieval: RetrievalEval | null
  answers: AnswersEval | null
  cache: CacheEval | null
  threshold: { file: string; timestamp: string; suggested_threshold?: number } | null
  redteam: {
    naive: RedteamRun | null
    defended: RedteamRun | null
    ablations: { label: string; layers: string[]; attack_success_rate: number; cases: number }[]
  }
}
