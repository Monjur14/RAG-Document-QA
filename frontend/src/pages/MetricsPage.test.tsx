import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { EvalResults } from '../api/evals'
import type { Metrics } from '../api/types'
import { fakeApi, renderAt } from '../test/render'

const metrics: Metrics = {
  requests: 40,
  error_rate: 0.025,
  cache_hit_rate: 0.3,
  total_cost_usd: 0,
  avg_cost_usd: 0,
  prompt_tokens: 1000,
  completion_tokens: 100,
  latency_ms: { p50: 543.9, p95: 2352 },
  llm_latency_ms: { p50: 500, p95: 2000 },
  by_status: { answered: 30, model_declined: 8, error: 1, blocked: 1 },
  by_model: { 'llama3.1:8b': 27 },
}

const evals: EvalResults = {
  retrieval: {
    file: 'corpus_20261005_085816.json',
    timestamp: '2026-10-05T08:57:33',
    questions: 102,
    k: 5,
    modes: {
      vector: { 'hit@1': 0.657, 'hit@3': 0.82, 'hit@5': 0.892, mrr: 0.744, avg_ms_per_query: 17.2 },
      'hybrid+rerank': {
        'hit@1': 0.735, 'hit@3': 0.86, 'hit@5': 0.912, mrr: 0.811, avg_ms_per_query: 172.5,
        by_format: { pdf: { 'hit@1': 0.71, 'hit@5': 0.878, mrr: 0.78, n: 49 } },
      },
    },
  },
  answers: null,
  cache: null,
  threshold: null,
  redteam: {
    naive: { file: 'redteam_naive_1.json', timestamp: '', label: 'naive (no defenses)', cases: 40, attack_success_rate: 0.475 },
    defended: { file: 'redteam_current_2.json', timestamp: '', label: 'current defenses', cases: 40, attack_success_rate: 0 },
    ablations: [{ label: 'layers: scan', layers: ['scan'], attack_success_rate: 0.225, cases: 40 }],
  },
}

afterEach(() => vi.unstubAllGlobals())

function stub(metricsFor: (url: string) => Metrics = () => metrics) {
  const seen: string[] = []
  vi.stubGlobal('fetch', async (input: string, init?: RequestInit) => {
    seen.push(input)
    if (input.startsWith('/api/metrics')) return Response.json(metricsFor(input))
    return fakeApi({
      'GET /health': () => Response.json({ status: 'ok' }),
      'GET /evals/latest': () => Response.json(evals),
    })(input, init)
  })
  return seen
}

it('shows request statistics', async () => {
  stub()
  renderAt('/metrics')
  expect(await screen.findByText('2.5%')).toBeInTheDocument()
  expect(screen.getByText('2,352 ms')).toBeInTheDocument()
  const byStatus = screen.getByRole('list', { name: 'Requests by status' })
  expect(within(byStatus).getByText('30 · 75%')).toBeInTheDocument()
  expect(within(byStatus).getByText('Error')).toBeInTheDocument()
})

it('switches to the last 24 hours', async () => {
  const seen = stub()
  renderAt('/metrics')
  await screen.findByText('2.5%')
  await userEvent.click(screen.getByRole('button', { name: 'Last 24 h' }))
  await waitFor(() => expect(seen).toContain('/api/metrics?hours=24'))
})

it('shows eval results, and a hint for the ones that were never run', async () => {
  stub()
  renderAt('/metrics')
  const retrieval = await screen.findByRole('region', { name: 'Retrieval quality' })
  expect(within(retrieval).getByText('used by the app')).toBeInTheDocument()
  expect(within(retrieval).getByText('0.81')).toBeInTheDocument()

  const redteam = screen.getByRole('region', { name: 'Red team' })
  expect(within(redteam).getByText('47.5%')).toBeInTheDocument()
  expect(within(redteam).getByText('0%')).toBeInTheDocument()

  expect(within(screen.getByRole('region', { name: 'Answer quality' })).getByText('python -m evals.answer_eval')).toBeInTheDocument()
})

it('has an empty state before any question is asked', async () => {
  stub(() => ({ ...metrics, requests: 0, by_status: {}, by_model: {} }))
  renderAt('/metrics')
  expect(await screen.findByText('No questions asked yet.')).toBeInTheDocument()
})
