import { ApiError } from '../api/client'

/** Turns a failed /ask call into a message a person can act on. */
export function describeAskError(err: unknown): { title: string; detail: string } {
  if (!(err instanceof ApiError)) return { title: 'Something went wrong', detail: 'Try again.' }
  switch (err.status) {
    case 0:
      return { title: 'Cannot reach the server', detail: 'Check that the backend is running on port 8000.' }
    case 429:
      return {
        title: 'Too many questions in a short time',
        detail: err.retryAfter ? `Try again in ${err.retryAfter} s.` : 'Wait a moment and try again.',
      }
    case 502:
      return { title: 'The language model is unavailable', detail: `${err.message}. Check that Ollama or your API provider is running.` }
    case 503:
      return { title: 'Database unavailable', detail: 'Check that the database container is running, then try again.' }
    case 422:
      return { title: 'The question was not accepted', detail: err.message }
    default:
      return { title: `Request failed (${err.status})`, detail: err.message }
  }
}
