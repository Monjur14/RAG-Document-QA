import { expect, it } from 'vitest'
import { ms, pct, usd } from './format'

it('pct trims trailing zeros', () => {
  expect(pct(0.475)).toBe('47.5%')
  expect(pct(0)).toBe('0%')
  expect(pct(1)).toBe('100%')
  expect(pct(null)).toBe('–')
})

it('usd keeps small costs readable', () => {
  expect(usd(0)).toBe('$0')
  expect(usd(0.00312)).toBe('$0.0031')
  expect(usd(1.5)).toBe('$1.50')
})

it('ms rounds and groups', () => {
  expect(ms(1234.5)).toBe('1,235 ms')
})
