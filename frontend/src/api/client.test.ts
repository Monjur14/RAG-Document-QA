import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './client'

function mockFetch(response: Response | Error) {
  const fn = response instanceof Error ? vi.fn().mockRejectedValue(response) : vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('prefixes /api and returns the JSON body', async () => {
    const fetchMock = mockFetch(Response.json({ status: 'ok' }))
    await expect(api('/health')).resolves.toEqual({ status: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith('/api/health', undefined)
  })

  it('returns undefined for 204 No Content', async () => {
    mockFetch(new Response(null, { status: 204 }))
    await expect(api('/documents/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('uses the FastAPI detail string as the error message', async () => {
    mockFetch(Response.json({ detail: 'Database unavailable' }, { status: 503 }))
    await expect(api('/documents')).rejects.toMatchObject({ status: 503, message: 'Database unavailable' })
  })

  it('reads the first validation message from a 422', async () => {
    mockFetch(Response.json({ detail: [{ msg: 'String should have at most 500 characters' }] }, { status: 422 }))
    await expect(api('/ask')).rejects.toMatchObject({ status: 422, message: 'String should have at most 500 characters' })
  })

  it('exposes Retry-After on a 429', async () => {
    mockFetch(Response.json({ detail: 'Too many requests. Try again in 12 s.' }, { status: 429, headers: { 'Retry-After': '12' } }))
    const err = await api('/ask').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).retryAfter).toBe(12)
  })

  it('reports status 0 when the server cannot be reached', async () => {
    mockFetch(new TypeError('Failed to fetch'))
    await expect(api('/health')).rejects.toMatchObject({ status: 0 })
  })

  it('falls back to the status text when the body is not JSON', async () => {
    mockFetch(new Response('<html>Bad gateway</html>', { status: 502, statusText: 'Bad Gateway' }))
    await expect(api('/ask')).rejects.toMatchObject({ status: 502, message: 'Bad Gateway' })
  })
})
