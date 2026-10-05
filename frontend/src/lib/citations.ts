// The backend asks the model to cite sources as [1] or [1, 2]. This splits an answer into plain text
// and citation markers so the markers can become buttons. Everything stays text: no HTML is ever built.

export type Segment = { kind: 'text'; text: string } | { kind: 'cite'; indexes: number[]; raw: string }

// Same pattern as _CITE in backend/app/answering.py.
const CITE = /\[(\d+(?:\s*,\s*\d+)*)\]/g

export function splitCitations(text: string): Segment[] {
  const segments: Segment[] = []
  let last = 0
  for (const match of text.matchAll(CITE)) {
    const start = match.index
    if (start > last) segments.push({ kind: 'text', text: text.slice(last, start) })
    segments.push({ kind: 'cite', indexes: match[1].split(',').map((n) => Number(n.trim())), raw: match[0] })
    last = start + match[0].length
  }
  if (last < text.length) segments.push({ kind: 'text', text: text.slice(last) })
  return segments
}
