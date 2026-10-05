import { expect, it } from 'vitest'
import { splitCitations } from './citations'

it('splits text and single citations', () => {
  expect(splitCitations('Run setup [1]. Then start [2].')).toEqual([
    { kind: 'text', text: 'Run setup ' },
    { kind: 'cite', indexes: [1], raw: '[1]' },
    { kind: 'text', text: '. Then start ' },
    { kind: 'cite', indexes: [2], raw: '[2]' },
    { kind: 'text', text: '.' },
  ])
})

it('handles grouped citations', () => {
  expect(splitCitations('Both [1, 3]')).toEqual([
    { kind: 'text', text: 'Both ' },
    { kind: 'cite', indexes: [1, 3], raw: '[1, 3]' },
  ])
})

it('leaves text without citations alone, including look-alike brackets', () => {
  expect(splitCitations('I don\'t know.')).toEqual([{ kind: 'text', text: "I don't know." }])
  expect(splitCitations('array[i] and [a]')).toEqual([{ kind: 'text', text: 'array[i] and [a]' }])
})

it('keeps HTML as literal text', () => {
  expect(splitCitations('<img src=x onerror=alert(1)> [1]')[0]).toEqual({ kind: 'text', text: '<img src=x onerror=alert(1)> ' })
})
