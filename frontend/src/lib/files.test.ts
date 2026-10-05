import { describe, expect, it } from 'vitest'
import { fileExtension, formatBytes, scannerNotes, validateFile } from './files'

const file = (name: string, bytes: number) => new File([new Uint8Array(bytes)], name)

describe('validateFile', () => {
  it('accepts supported types regardless of case', () => {
    expect(validateFile(file('Report.PDF', 10))).toBeNull()
    expect(validateFile(file('notes.markdown', 10))).toBeNull()
  })

  it('rejects unsupported types', () => {
    expect(validateFile(file('data.xlsx', 10))).toMatch(/not supported/)
    expect(validateFile(file('no-extension', 10))).toMatch(/not supported/)
  })

  it('rejects empty and oversized files', () => {
    expect(validateFile(file('a.txt', 0))).toMatch(/empty/)
    expect(validateFile(file('a.txt', 20 * 1024 * 1024 + 1))).toMatch(/larger than 20 MB/)
  })
})

it('fileExtension takes the last dot only', () => {
  expect(fileExtension('archive.tar.md')).toBe('.md')
})

it('formatBytes picks a sensible unit', () => {
  expect(formatBytes(512)).toBe('512 B')
  expect(formatBytes(2048)).toBe('2.0 KB')
  expect(formatBytes(3 * 1024 * 1024)).toBe('3.0 MB')
})

it('scannerNotes describes what the scanner did', () => {
  expect(scannerNotes({ quarantined: 0, sanitized: 0 })).toEqual([])
  expect(scannerNotes({ quarantined: 1, sanitized: 2 })).toEqual([
    '1 passage held back as suspicious',
    'Injected text removed from 2 passages',
  ])
})
