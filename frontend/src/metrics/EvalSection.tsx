import { ArrowRightIcon } from '@phosphor-icons/react'
import { useEvalResults } from '../api/hooks'
import type { AnswersEval, CacheEval, EvalResults, RetrievalEval } from '../api/evals'
import { Skeleton } from '../components/PageHeader'
import { ms, pct, shortDate } from '../lib/format'
import { BarList, Card, Missing, StatTile } from './parts'

// Retrieval modes in the order they build on each other. The app answers with hybrid + rerank.
const MODES: [string, string][] = [
  ['keyword', 'Keyword'],
  ['vector', 'Vector'],
  ['hybrid', 'Hybrid'],
  ['vector+rerank', 'Vector + rerank'],
  ['hybrid+rerank', 'Hybrid + rerank'],
]
const APP_MODE = 'hybrid+rerank'
const FORMAT_LABEL: Record<string, string> = { pdf: 'PDF', docx: 'Word', html: 'HTML', md: 'Markdown', txt: 'Text' }

const fromFile = (r: { timestamp?: string; file: string }) => `${shortDate(r.timestamp)} · ${r.file}`

function Retrieval({ r }: { r: RetrievalEval }) {
  const modes = MODES.filter(([key]) => r.modes[key])
  const formats = Object.entries(r.modes[APP_MODE]?.by_format ?? {}).sort((a, b) => b[1].n - a[1].n)
  return (
    <Card title="Retrieval quality" meta={fromFile(r)} className="lg:col-span-2">
      <p className="mb-4 text-fg-secondary">
        {r.questions} labeled questions. A hit means the passage with the answer was in the top results. MRR rewards ranking it first.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-left">
          <thead className="border-b border-line text-xs text-fg-muted">
            <tr>
              <th scope="col" className="py-2 pr-4 font-medium">Mode</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Hit@1</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Hit@{r.k}</th>
              <th scope="col" className="w-2/5 px-4 py-2 font-medium">MRR</th>
              <th scope="col" className="py-2 pl-4 text-right font-medium">Per query</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line font-mono text-xs">
            {modes.map(([key, label]) => {
              const m = r.modes[key]
              return (
                <tr key={key} className={key === APP_MODE ? 'bg-accent-soft' : undefined}>
                  <th scope="row" className="py-2 pr-4 font-sans text-sm font-normal">
                    {label}
                    {key === APP_MODE && <span className="ml-2 text-xs text-accent-text">used by the app</span>}
                  </th>
                  <td className="px-4 py-2 text-right">{pct(m['hit@1'])}</td>
                  <td className="px-4 py-2 text-right">{pct(m[`hit@${r.k}` as 'hit@5'] ?? m['hit@5'])}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 rounded-full bg-raised">
                        <div className="h-full rounded-full bg-accent" style={{ width: `${m.mrr * 100}%` }} />
                      </div>
                      <span className="w-10 text-right">{m.mrr.toFixed(2)}</span>
                    </div>
                  </td>
                  <td className="py-2 pl-4 text-right text-fg-secondary">{ms(m.avg_ms_per_query)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {formats.length > 0 && (
        <>
          <h4 className="mt-6 mb-3 text-xs font-medium text-fg-muted">Hit@{r.k} by format, hybrid + rerank</h4>
          <BarList
            label="Retrieval hit rate by format"
            max={1}
            rows={formats.map(([fmt, s]) => ({
              key: fmt,
              label: `${FORMAT_LABEL[fmt] ?? fmt} (${s.n})`,
              value: s['hit@5'],
              display: pct(s['hit@5']),
              title: `Hit@1 ${pct(s['hit@1'])}, MRR ${s.mrr.toFixed(2)}`,
            }))}
          />
        </>
      )}
    </Card>
  )
}

function Answers({ a }: { a: AnswersEval }) {
  const formats = Object.entries(a.answerable.by_format ?? {}).sort((x, y) => y[1].n - x[1].n)
  return (
    <Card title="Answer quality" meta={fromFile(a)}>
      <div className="grid grid-cols-2 gap-3">
        <StatTile label="Correct and cited" value={pct(a.answerable.success)} sub={`${a.answerable.n} answerable questions`} />
        <StatTile label="Citation supports answer" value={pct(a.answerable.citation_supports_given_answered)} sub="of answered questions" />
        <StatTile
          label="Correct refusals"
          value={pct(a.unanswerable?.refused)}
          sub={a.unanswerable ? `${a.unanswerable.n} questions the documents cannot answer` : undefined}
        />
        <StatTile label="p95 latency" value={ms(a.answerable.p95_ms)} sub={`p50 ${ms(a.answerable.p50_ms)} · ${a.answer_model ?? ''}`} />
      </div>
      {formats.length > 0 && (
        <>
          <h4 className="mt-6 mb-3 text-xs font-medium text-fg-muted">Correct and cited, by format</h4>
          <BarList
            label="Answer success by format"
            max={1}
            rows={formats.map(([fmt, s]) => ({
              key: fmt,
              label: `${FORMAT_LABEL[fmt] ?? fmt} (${s.n})`,
              value: s.success,
              display: pct(s.success),
            }))}
          />
        </>
      )}
    </Card>
  )
}

function Redteam({ rt }: { rt: EvalResults['redteam'] }) {
  const { naive, defended, ablations } = rt
  if (!naive && !defended) return <Card title="Red team"><Missing what="red team" command="python -m evals.redteam_eval" /></Card>
  return (
    <Card title="Red team" meta={defended ? fromFile(defended) : undefined}>
      <p className="mb-4 text-fg-secondary">
        Share of {defended?.cases ?? naive?.cases} prompt injection attacks that worked. Lower is better.
      </p>
      <div className="flex items-center gap-4">
        <div className="flex-1 rounded-xl bg-raised p-4">
          <p className="text-xs text-fg-muted">No defenses</p>
          <p className="mt-1 font-mono text-3xl">{pct(naive?.attack_success_rate)}</p>
        </div>
        <ArrowRightIcon size={20} className="shrink-0 text-fg-muted" aria-label="after adding defenses" />
        <div className="flex-1 rounded-xl bg-raised p-4">
          <p className="text-xs text-fg-muted">All defenses</p>
          <p className="mt-1 font-mono text-3xl">{pct(defended?.attack_success_rate)}</p>
        </div>
      </div>
      {defended?.legit_answer_preserved_on_poisoned_docs != null && (
        <p className="mt-3 text-xs text-fg-secondary">
          Legitimate answers still given from poisoned documents: {pct(defended.legit_answer_preserved_on_poisoned_docs)}
        </p>
      )}
      {ablations.length > 0 && (
        <>
          <h4 className="mt-6 mb-3 text-xs font-medium text-fg-muted">One layer at a time, attack success</h4>
          <BarList
            label="Attack success by defense layer"
            max={1}
            rows={[...ablations]
              // "no layers" first as the baseline, then the weakest single layer down to the strongest
              .sort((x, y) => (x.layers.length === 0 ? -1 : y.layers.length === 0 ? 1 : y.attack_success_rate - x.attack_success_rate))
              .map((a) => ({
              key: a.label,
              label: a.layers.length ? a.layers.join(' + ') : 'no layers',
              value: a.attack_success_rate,
              display: pct(a.attack_success_rate),
            }))}
          />
        </>
      )}
    </Card>
  )
}

function Cache({ c }: { c: CacheEval }) {
  const hits = c.cache_on.exact_hits + c.cache_on.semantic_hits
  return (
    <Card title="Caching" meta={fromFile(c)}>
      <p className="mb-4 text-fg-secondary">
        The same {c.workload.requests} requests replayed with the cache off and on. {hits} were served from the cache ({c.cache_on.exact_hits} exact,{' '}
        {c.cache_on.semantic_hits} similar at threshold {c.threshold}).
      </p>
      <BarList
        label="Savings with the cache on"
        max={1}
        rows={[
          { key: 'cost', label: 'Cost saved', value: c.savings.cost, display: pct(c.savings.cost) },
          { key: 'calls', label: 'Model calls saved', value: c.savings.llm_calls, display: pct(c.savings.llm_calls) },
          { key: 'latency', label: 'Average latency saved', value: c.savings.latency_avg, display: pct(c.savings.latency_avg) },
        ]}
      />
      {c.wrong_hits_on_near_misses && (
        <p className="mt-3 text-xs text-fg-secondary">
          Wrong cache hits on similar but different questions: {c.wrong_hits_on_near_misses.length}
        </p>
      )}
    </Card>
  )
}

export function EvalSection() {
  const { data, isPending, isError, error } = useEvalResults()

  if (isPending)
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-64 lg:col-span-2" />
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    )
  if (isError) return <p role="alert" className="text-danger">Could not load eval results. {error.message}</p>

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {data.retrieval ? <Retrieval r={data.retrieval} /> : <Card title="Retrieval quality" className="lg:col-span-2"><Missing what="retrieval" command="python -m evals.corpus_eval" /></Card>}
      {data.answers ? <Answers a={data.answers} /> : <Card title="Answer quality"><Missing what="answer" command="python -m evals.answer_eval" /></Card>}
      <Redteam rt={data.redteam} />
      {data.cache ? <Cache c={data.cache} /> : <Card title="Caching"><Missing what="cache" command="python -m evals.cache_eval" /></Card>}
      {data.threshold?.suggested_threshold != null && (
        <Card title="“I don't know” threshold" meta={fromFile(data.threshold)}>
          <p className="text-fg-secondary">
            Questions whose best passage scores below <span className="font-mono text-fg">{data.threshold.suggested_threshold.toFixed(3)}</span>{' '}
            are refused before the model is asked. This is the value the threshold eval suggested; the active one is{' '}
            <span className="font-mono">MIN_VECTOR_SCORE</span> in <span className="font-mono">.env</span>.
          </p>
        </Card>
      )}
    </div>
  )
}
