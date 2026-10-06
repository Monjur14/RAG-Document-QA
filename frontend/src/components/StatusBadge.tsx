import { LightningIcon } from '@phosphor-icons/react'
import type { AnswerStatus, CacheStatus } from '../api/types'
import { ANSWER_STATUS } from './answerStatus'

const badgeBase = 'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium'

export function StatusBadge({ status, label: override }: { status: AnswerStatus; label?: string }) {
  const { label, description, icon: BadgeIcon, className } = ANSWER_STATUS[status]
  return (
    <span className={`${badgeBase} ${className}`} title={description}>
      <BadgeIcon size={14} weight="bold" aria-hidden="true" />
      {override ?? label}
    </span>
  )
}

export function CacheBadge({ cache }: { cache: CacheStatus }) {
  if (cache === 'miss') return null
  return (
    <span
      className={`${badgeBase} text-accent-text ring-1 ring-accent/40 ring-inset`}
      title={cache === 'exact' ? 'Same question asked before.' : 'A very similar question was asked before.'}
    >
      <LightningIcon size={14} weight="bold" aria-hidden="true" />
      {cache === 'exact' ? 'Cached' : 'Cached, similar'}
    </span>
  )
}
