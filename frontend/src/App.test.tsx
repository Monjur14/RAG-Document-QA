import { screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { renderAt } from './test/render'

// Every request gets a fresh response: /health answers ok, /documents an empty list.
beforeEach(() =>
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(url.endsWith('/documents') ? [] : { status: 'ok' }))),
)
afterEach(() => vi.unstubAllGlobals())

it.each([
  ['/', 'Library'],
  ['/chat', 'Ask about your documents'],
  ['/metrics', 'Metrics'],
])('renders %s', (path, heading) => {
  renderAt(path)
  expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
})

it('marks the current page in the navigation', () => {
  renderAt('/chat')
  expect(screen.getByRole('link', { name: 'Chat' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('link', { name: 'Library' })).not.toHaveAttribute('aria-current')
})

it('shows the API as online when /health answers', async () => {
  renderAt('/')
  expect(await screen.findByText('API online')).toBeInTheDocument()
})

it('shows the API as offline when /health fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  renderAt('/')
  expect(await screen.findByText('API offline')).toBeInTheDocument()
})

it('shows a 404 page for unknown routes', () => {
  renderAt('/nope')
  expect(screen.getByRole('heading', { name: 'This page does not exist' })).toBeInTheDocument()
})
