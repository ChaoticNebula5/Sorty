import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { searchEvent } from '@/api/search'
import { createExport, getExportJob, getExportDownloadUrl } from '@/api/export'
import { getEvent } from '@/api/events'
import { Search, Loader2, Download, Package, Settings2, AlertCircle } from 'lucide-react'
import { StatusChip } from '@/components/ui/StatusChip'

export function EventSearch() {
  const { eventId } = useParams()
  
  const [query, setQuery] = useState('')
  const [includeDuplicates, setIncludeDuplicates] = useState(false)
  const [includeBlurry, setIncludeBlurry] = useState(false)
  const [includePending, setIncludePending] = useState(false)
  
  const [activeExportId, setActiveExportId] = useState<string | null>(null)

  // Fetch Event
  const { data: eventData, isError: isEventError } = useQuery({
    queryKey: ['event', eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
  })

  // Fetch Search Results
  const { data: searchData, isLoading: isSearchLoading } = useQuery({
    queryKey: ['search', eventId, query, includeDuplicates, includeBlurry, includePending],
    queryFn: () => searchEvent(eventId!, {
      q: query,
      include_duplicates: includeDuplicates,
      include_blurry: includeBlurry,
      include_pending: includePending,
      limit: 100
    }),
    enabled: !!eventId,
  })

  // Poll Export Job
  const { data: exportData } = useQuery({
    queryKey: ['export', activeExportId],
    queryFn: () => getExportJob(activeExportId!),
    enabled: !!activeExportId,
    refetchInterval: (query) => {
      const status = query.state.data?.data?.status
      if (status === 'completed' || status === 'failed') return false
      return 3000
    }
  })

  const exportMutation = useMutation({
    mutationFn: () => createExport(eventId!, {
      include_duplicates: includeDuplicates,
      include_blurry: includeBlurry,
      include_pending: includePending
    }),
    onSuccess: (data) => {
      if (data.data?.id) {
        setActiveExportId(data.data.id)
      }
    }
  })

  const results = searchData?.data || []
  const event = eventData?.data
  const exportJob = exportData?.data

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-border px-6 py-5 shrink-0">
        <div className="flex justify-between items-end">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Link to="/" className="hover:text-foreground">Library</Link>
              <span>/</span>
              <Link to={`/events/${eventId}`} className="hover:text-foreground">Event {eventId?.substring(0,8)}</Link>
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              {isEventError ? 'Event Unavailable' : (event ? event.name : 'Loading...')}
            </h1>
          </div>
          <Link
            to={`/events/${eventId}`}
            className="text-sm text-primary hover:underline"
          >
            Back to Event
          </Link>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col xl:flex-row">
        {/* Main Search Area */}
        <div className="flex flex-1 flex-col overflow-hidden bg-background">
          <div className="border-b border-border bg-surface p-4 shrink-0">
            <div className="flex flex-col gap-4 max-w-3xl">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search by tags, captions, or folders..."
                  className="w-full rounded-sm border border-border bg-card py-2 pl-9 pr-4 text-sm text-foreground focus:border-primary/60 focus:outline-none"
                />
              </div>

              <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includePending}
                    onChange={(e) => setIncludePending(e.target.checked)}
                    className="rounded-sm border-border bg-card text-primary focus:ring-primary/50 accent-primary"
                  />
                  Include Pending Review
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeDuplicates}
                    onChange={(e) => setIncludeDuplicates(e.target.checked)}
                    className="rounded-sm border-border bg-card text-primary focus:ring-primary/50 accent-primary"
                  />
                  Include Duplicates
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={includeBlurry}
                    onChange={(e) => setIncludeBlurry(e.target.checked)}
                    className="rounded-sm border-border bg-card text-primary focus:ring-primary/50 accent-primary"
                  />
                  Include Blurry/Rejected
                </label>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {isSearchLoading ? (
              <div className="flex h-32 items-center justify-center">
                <Loader2 className="size-6 animate-spin text-primary" />
              </div>
            ) : results.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-muted-foreground">
                No media found matching these filters.
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
                {results.map((item) => (
                  <div key={item.media_id} className="group relative aspect-square overflow-hidden rounded-md border border-border bg-card">
                    <img
                      src={item.thumbnail_url.startsWith('http') ? item.thumbnail_url : `${import.meta.env.VITE_API_BASE_URL || '/api'}${item.thumbnail_url}`}
                      alt="thumbnail"
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                      loading="lazy"
                    />
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-background/90 to-transparent p-2 pt-6">
                      <div className="flex items-center gap-1">
                        {item.quality_label && (
                          <StatusChip tone="info" className="text-[10px] px-1 py-0">{item.quality_label}</StatusChip>
                        )}
                        {item.review_status === 'approved' && (
                          <StatusChip tone="ok" className="text-[10px] px-1 py-0">Approved</StatusChip>
                        )}
                        {item.review_status === 'rejected' && (
                          <StatusChip tone="danger" className="text-[10px] px-1 py-0">Rejected</StatusChip>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar: Export Tool */}
        <div className="flex w-full shrink-0 flex-col border-t border-border bg-card xl:w-80 xl:border-l xl:border-t-0">
          <div className="border-b border-border p-4">
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Package className="size-4 text-muted-foreground" />
              ZIP Export Setup
            </h3>
          </div>
          
          <div className="flex flex-col gap-6 p-4">
            <div className="rounded-sm bg-surface p-4 border border-border text-sm">
              <div className="flex items-start gap-3">
                <Settings2 className="size-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-foreground">Export Configuration</p>
                  <p className="mt-1 text-muted-foreground">
                    This export will include all approved media matching your current filter toggles.
                  </p>
                </div>
              </div>
            </div>

            {!exportJob ? (
              <button
                onClick={() => exportMutation.mutate()}
                disabled={exportMutation.isPending}
                className="flex w-full items-center justify-center gap-2 rounded-sm bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {exportMutation.isPending ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                Generate ZIP Pack
              </button>
            ) : (
              <div className="rounded-md border border-border bg-surface overflow-hidden">
                <div className="p-4 border-b border-border flex justify-between items-center">
                  <span className="text-sm font-medium text-foreground">Export Status</span>
                  <StatusChip tone={exportJob.status === 'completed' ? 'ok' : exportJob.status === 'failed' ? 'danger' : 'info'}>
                    {exportJob.status}
                  </StatusChip>
                </div>
                
                <div className="p-4">
                  <div className="flex justify-between text-sm mb-3">
                    <span className="text-muted-foreground">Included Items:</span>
                    <span className="font-medium text-foreground">{exportJob.included_count}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-4">
                    <span className="text-muted-foreground">Excluded Items:</span>
                    <span className="font-medium text-foreground">{exportJob.excluded_count}</span>
                  </div>

                  {exportJob.status === 'processing' && (
                    <div className="flex items-center gap-2 text-sm text-primary">
                      <Loader2 className="size-4 animate-spin" />
                      Building ZIP archive...
                    </div>
                  )}

                  {exportJob.status === 'completed' && exportJob.download_url && (
                    <a
                      href={getExportDownloadUrl(exportJob.id)}
                      download
                      className="mt-2 flex w-full items-center justify-center gap-2 rounded-sm bg-ok px-4 py-2 text-sm font-medium text-ok-foreground transition-opacity hover:opacity-90"
                    >
                      <Download className="size-4" />
                      Download ZIP
                    </a>
                  )}

                  {exportJob.status === 'failed' && (
                    <div className="flex items-center gap-2 text-sm text-danger mt-2">
                      <AlertCircle className="size-4" />
                      {exportJob.error_message || 'Export failed'}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
