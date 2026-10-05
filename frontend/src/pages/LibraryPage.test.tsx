import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DocumentInfo, UploadResponse } from '../api/types'
import { fakeApi, renderAt } from '../test/render'

const doc = (over: Partial<DocumentInfo>): DocumentInfo => ({
  id: 1,
  filename: 'guide.md',
  file_type: 'md',
  status: 'indexed',
  error: null,
  created_at: '2026-10-05T09:30:00Z',
  chunk_count: 12,
  quarantined: 0,
  sanitized: 0,
  flags: [],
  ...over,
})

const uploaded = (over: Partial<UploadResponse> = {}): UploadResponse => ({
  document_id: 7,
  filename: 'new.md',
  file_type: 'md',
  status: 'indexed',
  sections: 2,
  chunks: 3,
  characters: 900,
  preview: [],
  quarantined: 0,
  sanitized: 0,
  flags: [],
  ...over,
})

const health = () => Response.json({ status: 'ok' })
const mdFile = (name = 'new.md') => new File(['# Title\nBody'], name, { type: 'text/markdown' })

afterEach(() => vi.unstubAllGlobals())

describe('document list', () => {
  it('lists documents with status, chunk count and scanner notes', async () => {
    vi.stubGlobal(
      'fetch',
      fakeApi({
        'GET /health': health,
        'GET /documents': () =>
          Response.json([
            doc({ id: 1, filename: 'guide.md' }),
            doc({ id: 2, filename: 'poisoned.html', file_type: 'html', quarantined: 1, sanitized: 2, flags: ['instruction_override'] }),
            doc({ id: 3, filename: 'broken.pdf', file_type: 'pdf', status: 'failed', error: 'boom', chunk_count: 0 }),
          ]),
      }),
    )
    renderAt('/')
    const table = await screen.findByRole('table')
    expect(within(table).getByText('guide.md')).toBeInTheDocument()
    expect(within(table).getByText('1 passage held back as suspicious')).toBeInTheDocument()
    expect(within(table).getByText('Injected text removed from 2 passages')).toBeInTheDocument()
    expect(within(table).getByText('boom')).toBeInTheDocument()
    expect(within(table).getByText('Failed')).toBeInTheDocument()
  })

  it('shows the server error and lets the user retry', async () => {
    let calls = 0
    vi.stubGlobal(
      'fetch',
      fakeApi({
        'GET /health': health,
        'GET /documents': () => (++calls === 1 ? Response.json({ detail: 'Database unavailable' }, { status: 503 }) : Response.json([])),
      }),
    )
    renderAt('/')
    expect(await screen.findByText('Database unavailable')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No documents yet')).toBeInTheDocument()
  })
})

describe('upload', () => {
  it('uploads a dropped file, shows the result and refreshes the list', async () => {
    let docs: DocumentInfo[] = []
    const upload = vi.fn(() => {
      docs = [doc({ id: 7, filename: 'new.md', chunk_count: 3, quarantined: 1 })]
      return Response.json(uploaded({ quarantined: 1 }))
    })
    vi.stubGlobal('fetch', fakeApi({ 'GET /health': health, 'GET /documents': () => Response.json(docs), 'POST /documents/upload': upload }))
    renderAt('/')
    await screen.findByText('No documents yet')

    const zone = screen.getByRole('region', { name: 'Upload documents' })
    const dataTransfer = { files: [mdFile()], types: ['Files'], dropEffect: 'none' }
    fireEvent.dragEnter(zone, { dataTransfer })
    expect(screen.getByText('Drop to upload')).toBeInTheDocument()
    fireEvent.drop(zone, { dataTransfer })

    const uploads = screen.getByRole('region', { name: 'Uploads' })
    expect(await within(uploads).findByText('Indexed into 3 chunks')).toBeInTheDocument()
    expect(within(uploads).getByText('1 passage held back as suspicious')).toBeInTheDocument()
    expect(await within(screen.getByRole('table')).findByText('new.md')).toBeInTheDocument()

    expect(upload).toHaveBeenCalledOnce()
    const body = (upload.mock.calls[0] as unknown as [RequestInit])[0].body as FormData
    expect((body.get('file') as File).name).toBe('new.md')
  })

  it('rejects an unsupported file without calling the server', async () => {
    const upload = vi.fn()
    vi.stubGlobal('fetch', fakeApi({ 'GET /health': health, 'GET /documents': () => Response.json([]), 'POST /documents/upload': upload }))
    renderAt('/')
    await userEvent.upload(screen.getByTestId('file-input'), new File(['x'], 'sheet.xlsx'), { applyAccept: false })
    expect(await screen.findByText(/not supported/)).toBeInTheDocument()
    expect(upload).not.toHaveBeenCalled()
  })

  it('shows the server reason when an upload is rejected', async () => {
    vi.stubGlobal(
      'fetch',
      fakeApi({
        'GET /health': health,
        'GET /documents': () => Response.json([]),
        'POST /documents/upload': () => Response.json({ detail: 'Malformed PDF' }, { status: 422 }),
      }),
    )
    renderAt('/')
    await userEvent.upload(screen.getByTestId('file-input'), mdFile('bad.md'))
    expect(await screen.findByText('Malformed PDF')).toBeInTheDocument()
  })
})

describe('delete', () => {
  it('asks for confirmation, then deletes and refreshes', async () => {
    let docs = [doc({ id: 5, filename: 'old.md' })]
    const del = vi.fn(() => {
      docs = []
      return new Response(null, { status: 204 })
    })
    vi.stubGlobal('fetch', fakeApi({ 'GET /health': health, 'GET /documents': () => Response.json(docs), 'DELETE /documents/5': del }))
    renderAt('/')
    const table = await screen.findByRole('table')

    await userEvent.click(within(table).getByRole('button', { name: 'Delete old.md' }))
    expect(del).not.toHaveBeenCalled()
    await userEvent.click(within(table).getByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(del).toHaveBeenCalledOnce())
    expect(await screen.findByText('No documents yet')).toBeInTheDocument()
  })

  it('cancel keeps the document', async () => {
    const del = vi.fn()
    vi.stubGlobal('fetch', fakeApi({ 'GET /health': health, 'GET /documents': () => Response.json([doc({ id: 5, filename: 'old.md' })]), 'DELETE /documents/5': del }))
    renderAt('/')
    const table = await screen.findByRole('table')
    await userEvent.click(within(table).getByRole('button', { name: 'Delete old.md' }))
    await userEvent.click(within(table).getByRole('button', { name: 'Cancel' }))
    expect(within(table).getByRole('button', { name: 'Delete old.md' })).toBeInTheDocument()
    expect(del).not.toHaveBeenCalled()
  })
})
