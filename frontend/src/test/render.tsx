import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { App } from '../App'

/** Renders the whole app at a route, with a fresh query cache per test. */
export function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

type Handler = (init: RequestInit | undefined) => Response | Promise<Response>

/** A fake fetch that answers by "METHOD /path". Unmatched requests fail the test loudly. */
export function fakeApi(routes: Record<string, Handler>) {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input).replace(/^\/api/, '')}`
    const handler = routes[key]
    if (!handler) throw new Error(`Unexpected request: ${key}`)
    return handler(init)
  }
}
