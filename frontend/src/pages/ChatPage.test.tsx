import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AskResponse } from '../api/types'
import { fakeApi, renderAt } from '../test/render'

const answer = (over: Partial<AskResponse> = {}): AskResponse => ({
  question: 'How do I install?',
  answer: 'Run the installer [1] and restart [2].',
  status: 'answered',
  citations: [
    { index: 1, chunk_id: 10, document_id: 1, source: 'guide.md', heading: 'Install', page: null, text: 'Run the installer and follow the prompts.' },
    { index: 2, chunk_id: 11, document_id: 1, source: 'manual.pdf', heading: null, page: 4, text: 'Restart the service after installing.' },
  ],
  confidence: 0.81,
  model: 'llama3.1:8b',
  prompt_tokens: 900,
  completion_tokens: 40,
  latency_ms: 1234.5,
  retrieved: 5,
  cache: 'miss',
  flags: [],
  ...over,
})

const base = { 'GET /health': () => Response.json({ status: 'ok' }), 'GET /documents': () => Response.json([]) }

async function ask(text: string) {
  await userEvent.type(screen.getByLabelText('Question'), text)
  await userEvent.click(screen.getByRole('button', { name: /^ask/i }))
}

afterEach(() => vi.unstubAllGlobals())

describe('asking', () => {
  it('sends the question and shows the cited answer', async () => {
    const post = vi.fn(() => Response.json(answer()))
    vi.stubGlobal('fetch', fakeApi({ ...base, 'POST /ask': post }))
    renderAt('/chat')
    await ask('How do I install?')

    expect(await screen.findByText('Answered')).toBeInTheDocument()
    expect(screen.getByText(/llama3\.1:8b · 1,235 ms/)).toBeInTheDocument()
    expect(JSON.parse((post.mock.calls[0] as unknown as [RequestInit])[0].body as string)).toEqual({
      question: 'How do I install?',
      file_types: null,
      document_ids: null,
    })
    expect(screen.getByLabelText('Question')).toHaveValue('')
  })

  it('Enter sends and Shift+Enter adds a line', async () => {
    const post = vi.fn(() => Response.json(answer()))
    vi.stubGlobal('fetch', fakeApi({ ...base, 'POST /ask': post }))
    renderAt('/chat')
    const box = screen.getByLabelText('Question')
    await userEvent.type(box, 'line one{Shift>}{Enter}{/Shift}line two')
    expect(box).toHaveValue('line one\nline two')
    await userEvent.type(box, '{Enter}')
    await waitFor(() => expect(post).toHaveBeenCalledOnce())
  })

  it('renders answers as text, never as HTML', async () => {
    const evil = '<img src=x onerror="alert(1)"> <b>bold</b>'
    vi.stubGlobal('fetch', fakeApi({ ...base, 'POST /ask': () => Response.json(answer({ answer: evil, citations: [] })) }))
    const { container } = renderAt('/chat')
    await ask('test')
    expect(await screen.findByText(evil)).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
  })

  it('shows "I don\'t know" with the confidence that caused it', async () => {
    vi.stubGlobal(
      'fetch',
      fakeApi({ ...base, 'POST /ask': () => Response.json(answer({ answer: "I don't know.", status: 'insufficient_evidence', citations: [], model: null, confidence: 0.31 })) }),
    )
    renderAt('/chat')
    await ask('What is the capital of Mars?')
    expect(await screen.findByText("I don't know", { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText(/confidence 0\.31/)).toBeInTheDocument()
  })

  it('sends filters, expanding file type groups to every extension', async () => {
    const post = vi.fn(() => Response.json(answer()))
    vi.stubGlobal('fetch', fakeApi({ ...base, 'POST /ask': post }))
    renderAt('/chat')
    await userEvent.click(screen.getByRole('button', { name: 'Filters' }))
    await userEvent.click(screen.getByRole('button', { name: 'Markdown' }))
    await ask('q')
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(JSON.parse((post.mock.calls[0] as unknown as [RequestInit])[0].body as string).file_types).toEqual(['md', 'markdown'])
  })
})

describe('citations', () => {
  it('opens the full passage from a citation chip', async () => {
    vi.stubGlobal('fetch', fakeApi({ ...base, 'POST /ask': () => Response.json(answer()) }))
    renderAt('/chat')
    await ask('How do I install?')
    await userEvent.click(await screen.findByRole('button', { name: 'Source 2: manual.pdf' }))

    const panel = screen.getByRole('dialog')
    expect(within(panel).getByText('Restart the service after installing.')).toBeInTheDocument()
    expect(within(panel).getByText('Page 4')).toBeInTheDocument()

    await userEvent.click(within(panel).getByRole('button', { name: 'Close passage' }))
    expect(screen.queryByText('Restart the service after installing.')).not.toBeInTheDocument()
  })

  it('leaves a marker as text when the backend dropped that citation', async () => {
    vi.stubGlobal('fetch', fakeApi({ ...base, 'POST /ask': () => Response.json(answer({ answer: 'See [7].', citations: [] , status: 'uncited'})) }))
    renderAt('/chat')
    await ask('q')
    expect(await screen.findByText('See [7].')).toBeInTheDocument()
    expect(screen.getByText('Unverified')).toBeInTheDocument()
  })
})

describe('errors', () => {
  it('explains rate limiting with the retry time, and retries', async () => {
    let calls = 0
    vi.stubGlobal(
      'fetch',
      fakeApi({
        ...base,
        'POST /ask': () =>
          ++calls === 1
            ? Response.json({ detail: 'Too many requests.' }, { status: 429, headers: { 'Retry-After': '9' } })
            : Response.json(answer()),
      }),
    )
    renderAt('/chat')
    await ask('q')
    expect(await screen.findByText('Too many questions in a short time')).toBeInTheDocument()
    expect(screen.getByText('Try again in 9 s.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Answered')).toBeInTheDocument()
  })

  it('explains a model outage', async () => {
    vi.stubGlobal(
      'fetch',
      fakeApi({ ...base, 'POST /ask': () => Response.json({ detail: 'The language model is unavailable: timeout' }, { status: 502 }) }),
    )
    renderAt('/chat')
    await ask('q')
    expect(await screen.findByText('The language model is unavailable')).toBeInTheDocument()
  })
})

it('keeps the conversation when leaving the page and coming back', async () => {
  vi.stubGlobal('fetch', fakeApi({ ...base, 'POST /ask': () => Response.json(answer()) }))
  renderAt('/chat')
  await ask('How do I install?')
  await screen.findByText('Answered')
  await userEvent.click(screen.getByRole('link', { name: 'Library' }))
  await userEvent.click(screen.getByRole('link', { name: 'Chat' }))
  expect(screen.getByText('Answered')).toBeInTheDocument()
})
