import { CheckCircleIcon, ProhibitIcon, QuestionIcon, WarningIcon } from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import type { AnswerStatus } from '../api/types'

interface BadgeStyle {
  label: string
  description: string
  icon: Icon
  className: string
}

// Two backend statuses mean the same thing to the reader, so they share the "I don't know" badge.
// The description (shown as a tooltip) keeps the real reason visible.
export const ANSWER_STATUS: Record<AnswerStatus, BadgeStyle> = {
  answered: {
    label: 'Answered',
    description: 'Grounded in the cited passages.',
    icon: CheckCircleIcon,
    className: 'bg-ok-soft text-ok',
  },
  insufficient_evidence: {
    label: "I don't know",
    description: 'Retrieval confidence was below the threshold, so the model was not asked.',
    icon: QuestionIcon,
    className: 'bg-warn-soft text-warn',
  },
  model_declined: {
    label: "I don't know",
    description: 'The model read the passages and said they do not answer the question.',
    icon: QuestionIcon,
    className: 'bg-warn-soft text-warn',
  },
  uncited: {
    label: 'Unverified',
    description: 'The answer carried no valid citations, so it cannot be checked against your documents.',
    icon: WarningIcon,
    className: 'bg-caution-soft text-caution',
  },
  blocked: {
    label: 'Blocked',
    description: 'A guardrail stopped this request or its answer.',
    icon: ProhibitIcon,
    className: 'bg-danger-soft text-danger',
  },
}
