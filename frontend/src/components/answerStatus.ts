import { CheckCircleIcon, ProhibitIcon, QuestionIcon, WarningIcon } from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import type { AnswerStatus } from '../api/types'

interface BadgeStyle {
  label: string // shown on an answer in the chat
  metricLabel: string // shown on the metrics page, where every status is counted separately
  reason: string // one short line on what happened, for the metrics page
  description: string
  icon: Icon
  className: string
}

// Two backend statuses mean the same thing to the reader of an answer, so the chat shows both as "I don't know"
// (and explains which one under the answer). The metrics page counts them separately, with their own names.
export const ANSWER_STATUS: Record<AnswerStatus, BadgeStyle> = {
  answered: {
    label: 'Answered',
    metricLabel: 'Answered',
    reason: 'grounded in the cited passages',
    description: 'Grounded in the cited passages.',
    icon: CheckCircleIcon,
    className: 'bg-ok-soft text-ok',
  },
  insufficient_evidence: {
    label: "I don't know",
    metricLabel: 'No relevant passage',
    reason: 'refused before the model was asked',
    description: 'Retrieval confidence was below the threshold, so the model was not asked.',
    icon: QuestionIcon,
    className: 'bg-warn-soft text-warn',
  },
  model_declined: {
    label: "I don't know",
    metricLabel: 'Model declined',
    reason: "the passages didn't contain the answer",
    description: 'The model read the passages and said they do not answer the question.',
    icon: QuestionIcon,
    className: 'bg-warn-soft text-warn',
  },
  uncited: {
    label: 'Unverified',
    metricLabel: 'Unverified',
    reason: 'answer had no valid citation',
    description: 'The answer carried no valid citations, so it cannot be checked against your documents.',
    icon: WarningIcon,
    className: 'bg-caution-soft text-caution',
  },
  blocked: {
    label: 'Blocked',
    metricLabel: 'Blocked',
    reason: 'stopped by a security guardrail',
    description: 'A guardrail stopped this request or its answer.',
    icon: ProhibitIcon,
    className: 'bg-danger-soft text-danger',
  },
}
