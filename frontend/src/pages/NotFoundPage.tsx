import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="py-24 text-center">
      <p className="font-mono text-xs text-fg-muted">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">This page does not exist</h1>
      <Link to="/" className="mt-6 inline-block rounded-lg px-3 py-2 font-semibold text-accent-text hover:bg-accent-soft">
        Back to the library
      </Link>
    </div>
  )
}
