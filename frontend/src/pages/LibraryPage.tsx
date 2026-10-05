import { DocumentTable } from '../components/DocumentTable'
import { PageHeader } from '../components/PageHeader'
import { UploadList } from '../components/UploadList'
import { UploadZone } from '../components/UploadZone'
import { useUploadQueue } from '../hooks/useUploadQueue'

export function LibraryPage() {
  const uploads = useUploadQueue()

  return (
    <>
      <PageHeader
        title="Library"
        description="Upload documents to search and ask about. Every file is scanned for hidden instructions before it is indexed."
      />

      <UploadZone onFiles={uploads.add} />
      <UploadList items={uploads.items} onDismiss={uploads.dismiss} onClear={uploads.clearFinished} />

      <section aria-label="Documents" className="mt-8 overflow-hidden rounded-xl border border-line bg-surface">
        <DocumentTable />
      </section>
    </>
  )
}
