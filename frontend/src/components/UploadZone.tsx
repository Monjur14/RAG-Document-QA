import { UploadSimpleIcon } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { ALLOWED_EXTENSIONS, MAX_UPLOAD_MB } from '../api/types'

const hasFiles = (e: DragEvent | globalThis.DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files')

/**
 * Drop target plus a normal file picker (the picker is what keyboard and phone users get).
 * The browser only allows a drop if dragover calls preventDefault, which is why that handler exists.
 */
export function UploadZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  // dragenter/dragleave also fire when the pointer moves over child elements, so count them
  // instead of toggling, or the highlight flickers.
  const depth = useRef(0)

  // A file dropped anywhere else on the page would make the browser open it and leave the app.
  useEffect(() => {
    const block = (e: globalThis.DragEvent) => {
      if (hasFiles(e)) e.preventDefault()
    }
    window.addEventListener('dragover', block)
    window.addEventListener('drop', block)
    return () => {
      window.removeEventListener('dragover', block)
      window.removeEventListener('drop', block)
    }
  }, [])

  function onDragEnter(e: DragEvent) {
    if (!hasFiles(e)) return
    e.preventDefault()
    depth.current += 1
    setDragging(true)
  }

  function onDragOver(e: DragEvent) {
    if (!hasFiles(e)) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }

  function onDragLeave() {
    depth.current = Math.max(0, depth.current - 1)
    if (depth.current === 0) setDragging(false)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    depth.current = 0
    setDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) onFiles(files)
  }

  return (
    <section
      aria-label="Upload documents"
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      data-dragging={dragging || undefined}
      className="rounded-xl border border-dashed border-line-strong bg-surface p-8 text-center transition-colors duration-150 data-dragging:border-solid data-dragging:border-accent data-dragging:bg-accent-soft"
    >
      <UploadSimpleIcon
        size={28}
        className={`mx-auto transition-colors duration-150 ${dragging ? 'text-accent-text' : 'text-fg-muted'}`}
        aria-hidden="true"
      />
      <p className="mt-3 font-medium">
        {dragging ? (
          'Drop to upload'
        ) : (
          <>
            Drop files here, or{' '}
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="rounded-md font-semibold text-accent-text underline-offset-4 hover:underline"
            >
              choose files
            </button>
          </>
        )}
      </p>
      <p className="mt-1 text-xs text-fg-muted">PDF, Word, HTML, Markdown or text, up to {MAX_UPLOAD_MB}&nbsp;MB each</p>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ALLOWED_EXTENSIONS.join(',')}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        data-testid="file-input"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          e.target.value = '' // so choosing the same file again still fires onChange
          if (files.length > 0) onFiles(files)
        }}
      />
    </section>
  )
}
