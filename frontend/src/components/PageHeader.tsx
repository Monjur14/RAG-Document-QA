import type { ReactNode } from 'react'

export function PageHeader({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-fg-secondary">{description}</p>
      </div>
      {actions}
    </div>
  )
}

/** Gray block shaped like the content that will replace it. Used while data loads. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-raised ${className}`} aria-hidden="true" />
}
