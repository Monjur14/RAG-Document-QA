import {
  ArrowClockwiseIcon,
  CheckCircleIcon,
  CircleNotchIcon,
  FileDocIcon,
  FileHtmlIcon,
  FileIcon,
  FileMdIcon,
  FilePdfIcon,
  FilesIcon,
  FileTxtIcon,
  ShieldWarningIcon,
  TrashIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import { useState } from 'react'
import { useDeleteDocument, useDocuments } from '../api/hooks'
import type { DocumentInfo } from '../api/types'
import { formatDate, scannerNotes } from '../lib/files'
import { Skeleton } from './PageHeader'

const TYPE_ICON: Record<string, Icon> = {
  pdf: FilePdfIcon,
  docx: FileDocIcon,
  html: FileHtmlIcon,
  htm: FileHtmlIcon,
  md: FileMdIcon,
  markdown: FileMdIcon,
  txt: FileTxtIcon,
}

const badge = 'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium'

function DocStatus({ status }: { status: string }) {
  if (status === 'indexed')
    return (
      <span className={`${badge} bg-ok-soft text-ok`}>
        <CheckCircleIcon size={14} weight="bold" aria-hidden="true" />
        Indexed
      </span>
    )
  if (status === 'failed')
    return (
      <span className={`${badge} bg-danger-soft text-danger`}>
        <WarningCircleIcon size={14} weight="bold" aria-hidden="true" />
        Failed
      </span>
    )
  return (
    <span className={`${badge} bg-raised text-fg-secondary`}>
      <CircleNotchIcon size={14} weight="bold" className="animate-spin" aria-hidden="true" />
      Indexing
    </span>
  )
}

/** File name with the failure reason or scanner notes underneath, shared by the table and the phone cards. */
function DocName({ doc }: { doc: DocumentInfo }) {
  const TypeIcon = TYPE_ICON[doc.file_type] ?? FileIcon
  const notes = scannerNotes(doc)
  return (
    <div className="flex min-w-0 items-start gap-2">
      <TypeIcon size={18} className="mt-px shrink-0 text-fg-muted" aria-label={`${doc.file_type.toUpperCase()} file`} role="img" />
      <div className="min-w-0">
        <p className="truncate font-medium" title={doc.filename}>
          {doc.filename}
        </p>
        {doc.status === 'failed' && doc.error && <p className="mt-1 text-xs text-danger">{doc.error}</p>}
        {notes.map((note) => (
          <p key={note} className="mt-1 flex items-center gap-1 text-xs text-caution" title={doc.flags.join(', ')}>
            <ShieldWarningIcon size={14} weight="bold" className="shrink-0" aria-hidden="true" />
            {note}
          </p>
        ))}
      </div>
    </div>
  )
}

/** Two-step delete: the first click asks, the second deletes. No browser confirm() dialog. */
function DeleteControl({ doc }: { doc: DocumentInfo }) {
  const [confirming, setConfirming] = useState(false)
  const del = useDeleteDocument()

  if (del.isError)
    return (
      <span className="text-xs text-danger" role="alert">
        Could not delete. {del.error.message}
      </span>
    )

  if (!confirming)
    return (
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className="rounded-md p-2 text-fg-muted transition-colors duration-150 hover:bg-danger-soft hover:text-danger"
        aria-label={`Delete ${doc.filename}`}
      >
        <TrashIcon size={16} aria-hidden="true" />
      </button>
    )

  return (
    <span className="inline-flex items-center gap-1">
      <button
        type="button"
        autoFocus
        disabled={del.isPending}
        onClick={() => del.mutate(doc.id)}
        className="rounded-md bg-danger px-2 py-1 text-xs font-semibold text-white transition duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
      >
        {del.isPending ? 'Deleting' : 'Delete'}
      </button>
      <button
        type="button"
        disabled={del.isPending}
        onClick={() => setConfirming(false)}
        className="rounded-md px-2 py-1 text-xs font-semibold text-fg-secondary hover:bg-hover hover:text-fg"
      >
        Cancel
      </button>
    </span>
  )
}

export function DocumentTable() {
  const { data, isPending, isError, error, refetch, isFetching } = useDocuments()

  if (isPending)
    return (
      <div className="space-y-4 p-4" aria-label="Loading documents">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-24" />
          </div>
        ))}
      </div>
    )

  if (isError)
    return (
      <div className="px-4 py-12 text-center" role="alert">
        <WarningCircleIcon size={28} className="mx-auto text-danger" aria-hidden="true" />
        <p className="mt-3 font-medium">Could not load documents</p>
        <p className="mt-1 text-fg-secondary">{error.message}</p>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-line-strong px-3 py-2 font-semibold transition duration-150 hover:bg-hover active:scale-[0.98] disabled:opacity-50"
        >
          <ArrowClockwiseIcon size={16} aria-hidden="true" />
          Try again
        </button>
      </div>
    )

  if (data.length === 0)
    return (
      <div className="px-4 py-12 text-center">
        <FilesIcon size={28} className="mx-auto text-fg-muted" aria-hidden="true" />
        <p className="mt-3 font-medium">No documents yet</p>
        <p className="mt-1 text-fg-secondary">Upload a file above to get started.</p>
      </div>
    )

  return (
    <>
      {/* Tablet and desktop: a table */}
      <table className="hidden w-full table-fixed text-left sm:table">
        <thead className="border-b border-line text-xs text-fg-muted">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">Name</th>
            <th scope="col" className="w-32 px-4 py-3 font-medium">Status</th>
            <th scope="col" className="w-20 px-4 py-3 text-right font-medium">Chunks</th>
            <th scope="col" className="hidden w-48 px-4 py-3 font-medium md:table-cell">Added</th>
            <th scope="col" className="w-36 px-4 py-3"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {data.map((doc) => (
            <tr key={doc.id} className="align-top">
              <td className="px-4 py-3"><DocName doc={doc} /></td>
              <td className="px-4 py-3"><DocStatus status={doc.status} /></td>
              <td className="px-4 py-3 text-right font-mono">{doc.chunk_count}</td>
              <td className="hidden px-4 py-3 text-fg-secondary md:table-cell">{formatDate(doc.created_at)}</td>
              <td className="px-4 py-2 text-right"><DeleteControl doc={doc} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Phone: one card per document */}
      <ul className="divide-y divide-line sm:hidden">
        {data.map((doc) => (
          <li key={doc.id} className="flex items-start gap-2 p-4">
            <div className="min-w-0 flex-1">
              <DocName doc={doc} />
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-fg-secondary">
                <DocStatus status={doc.status} />
                <span className="font-mono">{doc.chunk_count} chunks</span>
                <span>{formatDate(doc.created_at)}</span>
              </div>
            </div>
            <DeleteControl doc={doc} />
          </li>
        ))}
      </ul>
    </>
  )
}
