import { BooksIcon, ChartBarIcon, ChatsCircleIcon, FileTextIcon } from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import { NavLink, Outlet } from 'react-router'
import { useHealth } from '../api/hooks'

const NAV: { to: string; label: string; icon: Icon }[] = [
  { to: '/', label: 'Library', icon: BooksIcon },
  { to: '/chat', label: 'Chat', icon: ChatsCircleIcon },
  { to: '/metrics', label: 'Metrics', icon: ChartBarIcon },
]

function HealthIndicator() {
  const { isPending, isError } = useHealth()
  const state = isPending ? 'checking' : isError ? 'offline' : 'online'
  const label = { checking: 'Checking API', offline: 'API offline', online: 'API online' }[state]
  const dot = { checking: 'bg-fg-muted', offline: 'bg-danger', online: 'bg-ok' }[state]

  return (
    <div className="flex items-center gap-2 text-xs text-fg-secondary" role="status" title={label}>
      <span className={`size-2 rounded-full ${dot}`} aria-hidden="true" />
      <span className="sr-only sm:not-sr-only">{label}</span>
    </div>
  )
}

export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only rounded-lg bg-accent px-3 py-2 font-semibold text-white focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:gap-6 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 rounded-md font-semibold">
            <FileTextIcon size={20} weight="duotone" className="text-accent-text" aria-hidden="true" />
            <span className="hidden sm:inline">Document Q&amp;A</span>
            <span className="sr-only sm:hidden">Document Q&amp;A home</span>
          </NavLink>

          <nav aria-label="Main" className="flex flex-1 items-center gap-1">
            {NAV.map(({ to, label, icon: NavIcon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  [
                    'flex items-center gap-2 rounded-lg px-3 py-2 font-medium transition-colors duration-150',
                    isActive ? 'bg-accent-soft text-accent-text' : 'text-fg-secondary hover:bg-hover hover:text-fg',
                  ].join(' ')
                }
              >
                {({ isActive }) => (
                  <>
                    <NavIcon size={16} weight={isActive ? 'fill' : 'regular'} aria-hidden="true" />
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          <HealthIndicator />
        </div>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 outline-none sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
