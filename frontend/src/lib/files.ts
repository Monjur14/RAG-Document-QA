import { ALLOWED_EXTENSIONS, MAX_UPLOAD_MB } from '../api/types'
import type { DocumentInfo } from '../api/types'

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot === -1 ? '' : name.slice(dot).toLowerCase()
}

/**
 * Quick checks before sending a file, so obvious mistakes fail instantly.
 * The server repeats every check; this is for feedback, not security.
 * Returns the reason the file is rejected, or null if it can be sent.
 */
export function validateFile(file: File): string | null {
  if (!ALLOWED_EXTENSIONS.includes(fileExtension(file.name))) {
    return 'This file type is not supported. Use PDF, Word, HTML, Markdown or text.'
  }
  if (file.size === 0) return 'The file is empty.'
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `The file is larger than ${MAX_UPLOAD_MB} MB.`
  return null
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** Plain-language notes about what the ingestion scanner did to a document. */
export function scannerNotes(doc: Pick<DocumentInfo, 'quarantined' | 'sanitized'>): string[] {
  const notes: string[] = []
  if (doc.quarantined > 0) notes.push(`${plural(doc.quarantined, 'passage', 'passages')} held back as suspicious`)
  if (doc.sanitized > 0) notes.push(`Injected text removed from ${plural(doc.sanitized, 'passage', 'passages')}`)
  return notes
}

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : dateFormat.format(date)
}
