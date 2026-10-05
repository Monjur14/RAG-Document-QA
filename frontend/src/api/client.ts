// The only place that calls fetch. Every request goes to /api/*, which Vite forwards to FastAPI.

export class ApiError extends Error {
  readonly status: number // 0 means the server could not be reached at all
  readonly retryAfter: number | null // seconds, from the Retry-After header on a 429

  constructor(status: number, message: string, retryAfter: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
  }
}

/** FastAPI puts the reason in `detail`: a string for HTTPException, a list for validation errors. */
async function readDetail(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg
    }
  } catch {
    // Not JSON (for example a proxy error page). Fall through to the status text.
  }
  return res.statusText || `Request failed with status ${res.status}`
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running.')
  }

  if (!res.ok) {
    const retry = Number(res.headers.get('Retry-After'))
    throw new ApiError(res.status, await readDetail(res), Number.isFinite(retry) && retry > 0 ? retry : null)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
