import { useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getEvent } from '@/api/events'
import { uploadMediaBatch, getJobStatus } from '@/api/jobs'
import { UploadCloud, Loader2, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { StatusChip } from '@/components/ui/StatusChip'
import { useDropzone } from 'react-dropzone'
import type { BatchJob } from '@/api/types'

export function EventDetail() {
  const { eventId } = useParams()
  
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)

  const { data: eventData, isLoading: isEventLoading, isError: isEventError } = useQuery({
    queryKey: ['event', eventId],
    queryFn: () => getEvent(eventId!),
    enabled: !!eventId,
  })

  // Poll Job Status if we have an active job
  const { data: jobData } = useQuery({
    queryKey: ['job', activeJobId],
    queryFn: () => getJobStatus(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const status = query.state.data?.data?.status
      if (status && ['completed', 'failed', 'partial_failed', 'waiting_for_review', 'reviewed'].includes(status)) {
        return false // Stop polling on terminal/wait states
      }
      return 2000 // Poll every 2 seconds
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => uploadMediaBatch(eventId!, files, (p) => setUploadProgress(p)),
    onSuccess: (data) => {
      if (data.data?.job_id) {
        setActiveJobId(data.data.job_id)
      }
      setUploadProgress(0) // reset after upload
    },
    onError: () => {
      setUploadProgress(0)
    }
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      uploadMutation.mutate(acceptedFiles)
    }
  }, [uploadMutation])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop })

  const event = eventData?.data
  const job = jobData?.data

  if (isEventError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2">
        <AlertCircle className="size-8 text-danger" />
        <h2 className="text-xl font-semibold text-foreground">Failed to load Event</h2>
        <p className="text-sm text-muted-foreground">The event could not be found or the server is down.</p>
        <Link to="/" className="mt-4 text-sm text-primary hover:underline">Back to Library</Link>
      </div>
    )
  }

  if (isEventLoading || !event) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="size-6 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-6 py-5">
        <div className="mono-label text-muted-foreground">Workspace / Events / {event.id}</div>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-foreground">
          {event.name}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {event.event_type} · Created {new Date(event.created_at).toLocaleDateString()}
        </p>

        <div className="mt-4 flex gap-3">
          <Link
            to={`/events/${eventId}/review`}
            className="flex items-center gap-2 rounded-sm border border-border bg-surface px-4 py-2 text-sm text-foreground transition-colors hover:bg-elevated"
          >
            Review Queue
          </Link>
          <Link
            to={`/events/${eventId}/search`}
            className="flex items-center gap-2 rounded-sm border border-border bg-surface px-4 py-2 text-sm text-foreground transition-colors hover:bg-elevated"
          >
            Search & Export
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 p-6 xl:grid-cols-[1fr_400px]">
        {/* Left: Dropzone */}
        <div className="flex flex-col gap-5">
          <div
            {...getRootProps()}
            className={`relative flex flex-col items-center justify-center gap-3 rounded-md border border-dashed px-6 py-12 text-center transition-colors cursor-pointer ${
              isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-border bg-card hover:border-primary/40'
            }`}
          >
            <input {...getInputProps()} />
            <div className="flex size-12 items-center justify-center rounded-md border border-border bg-surface text-primary">
              <UploadCloud className="size-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">
                Drop event photos here, or click to browse
              </p>
              <p className="mono-label mt-1 text-muted-foreground">
                JPG · PNG · Supported by backend
              </p>
            </div>
          </div>

          {/* Upload Progress Bar */}
          {uploadMutation.isPending && (
            <div className="overflow-hidden rounded-md border border-border bg-card">
              <div className="px-4 py-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground flex items-center gap-2">
                    <Loader2 className="size-4 animate-spin text-primary" />
                    Uploading batch to server...
                  </span>
                  <span className="mono-label text-muted-foreground">{uploadProgress}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-300"
                    style={{ width: `${Math.max(uploadProgress, 5)}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {uploadMutation.isError && (
            <div className="rounded-md border border-danger/30 bg-danger/10 p-4">
              <p className="text-sm text-danger flex items-center gap-2">
                <AlertCircle className="size-4" />
                Upload Failed: {uploadMutation.error?.message}
              </p>
            </div>
          )}
        </div>

        {/* Right: Active Job Tracker */}
        <div className="flex flex-col gap-5">
          {job ? (
            <JobTracker job={job} />
          ) : (
            <div className="rounded-md border border-border bg-card p-6 text-center text-muted-foreground flex flex-col items-center justify-center min-h-[200px]">
              <Clock className="size-6 mb-2 opacity-50" />
              <p className="text-sm">No active batch jobs.</p>
              <p className="text-xs mt-1">Upload files to start processing.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function JobTracker({ job }: { job: BatchJob }) {
  // Mapping the backend job status to a friendly UI stage
  const stages = [
    { id: 'queued', label: 'Queued', icon: Clock },
    { id: 'processing', label: 'Processing Media', icon: Loader2 },
    { id: 'waiting_for_review', label: 'Human Review Needed', icon: AlertCircle },
    { id: 'reviewed', label: 'Review Completed', icon: CheckCircle2 },
    { id: 'completed', label: 'Job Finished', icon: CheckCircle2 },
  ]

  let activeIndex = stages.findIndex(s => s.id === job.status)
  if (activeIndex === -1) activeIndex = 0 // fallback
  if (job.status === 'failed' || job.status === 'partial_failed') {
    activeIndex = stages.length // mark all as done/failed visually
  }

  return (
    <div className="overflow-hidden rounded-md border border-border bg-card">
      <div className="border-b border-border px-4 py-3 flex justify-between items-center">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Active Processing Job</h2>
          <p className="mono-label mt-0.5 text-muted-foreground">{job.id}</p>
        </div>
        <StatusChip tone={job.status === 'failed' ? 'danger' : job.status === 'completed' ? 'ok' : 'info'}>
          {job.status}
        </StatusChip>
      </div>

      <div className="px-4 py-4">
        <div className="flex justify-between text-sm mb-4">
          <div className="flex flex-col">
            <span className="mono-label text-muted-foreground">Processed</span>
            <span className="font-medium text-foreground">{job.processed_files} / {job.total_files}</span>
          </div>
          <div className="flex flex-col">
            <span className="mono-label text-muted-foreground">Needs Review</span>
            <span className="font-medium text-warn">{job.needs_review_count}</span>
          </div>
          <div className="flex flex-col">
            <span className="mono-label text-muted-foreground">Errors</span>
            <span className="font-medium text-danger">{job.failed_files}</span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="h-2 w-full overflow-hidden rounded-full bg-surface mb-6">
          <div
            className={`h-full rounded-full transition-all duration-500 ${job.status.includes('fail') ? 'bg-danger' : 'bg-primary'}`}
            style={{ width: `${job.total_files > 0 ? (job.processed_files / job.total_files) * 100 : 0}%` }}
          />
        </div>

        <div className="flex flex-col gap-3">
          {stages.map((stage, idx) => {
            const Icon = stage.icon
            const isPast = idx < activeIndex || job.status === 'completed'
            const isCurrent = idx === activeIndex && !['completed', 'failed', 'partial_failed'].includes(job.status)
            
            let color = 'text-muted-foreground'
            if (isCurrent) color = 'text-primary'
            if (isPast) color = 'text-ok'
            
            return (
              <div key={stage.id} className="flex items-center gap-3">
                {isCurrent && stage.id !== 'waiting_for_review' ? (
                  <Loader2 className={`size-4 animate-spin ${color}`} />
                ) : (
                  <Icon className={`size-4 ${color}`} />
                )}
                <span className={`text-sm ${isCurrent || isPast ? 'text-foreground' : 'text-muted-foreground'}`}>
                  {stage.label}
                </span>
              </div>
            )
          })}
        </div>

        {job.status === 'waiting_for_review' && (
          <div className="mt-6">
            <Link
              to={`/events/${job.event_id}/review`}
              className="flex w-full items-center justify-center gap-2 rounded-sm bg-warn px-4 py-2 text-sm font-medium text-warn-foreground text-background transition-opacity hover:opacity-90"
            >
              Start Review Queue
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
