import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getReviewQueue, updateReviewDecision } from '@/api/review'
import { getEventJobs } from '@/api/events'
import { resumeJob } from '@/api/jobs'
import { Check, X, Flag, AlertCircle, Loader2, Info, ChevronRight, ChevronLeft, PlayCircle, Undo2 } from 'lucide-react'
import { StatusChip } from '@/components/ui/StatusChip'
import type { ReviewQueueItem, ReviewDecisionUpdate } from '@/api/types'
import { cn } from '@/lib/utils'

export function ReviewQueue() {
  const { eventId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [activeIndex, setActiveIndex] = useState(0)
  const [showUndo, setShowUndo] = useState(false)
  const stagedRef = useRef<{ item: ReviewQueueItem, payload: ReviewDecisionUpdate } | null>(null)
  
  const { data: queueData, isLoading: isQueueLoading, isError: isQueueError } = useQuery({
    queryKey: ['review-queue', eventId],
    queryFn: () => getReviewQueue(eventId!),
    enabled: !!eventId,
  })

  const { data: jobsData, refetch: refetchJobs } = useQuery({
    queryKey: ['event-jobs', eventId],
    queryFn: () => getEventJobs(eventId!),
    enabled: !!eventId,
  })

  const queue = queueData?.data || []
  const activeItem = queue[activeIndex] || null

  // Find a job waiting for review
  const waitingJob = jobsData?.data?.find(j => j.status === 'waiting_for_review')

  // Keep active index in bounds
  useEffect(() => {
    if (queue.length > 0 && activeIndex >= queue.length) {
      setActiveIndex(Math.max(0, queue.length - 1))
    }
  }, [queue.length, activeIndex])

  // Fire-and-forget commit on unmount
  useEffect(() => {
    return () => {
      if (stagedRef.current) {
        updateReviewDecision({
          mediaId: stagedRef.current.item.media_id,
          payload: stagedRef.current.payload
        }).catch(console.error)
      }
    }
  }, [])

  const decisionMutation = useMutation({
    mutationFn: (params: { mediaId: string, payload: ReviewDecisionUpdate }) => updateReviewDecision(params),
    onSuccess: () => {
      // Optimistic update handles UI, no need to invalidate immediately
    }
  })

  const handleDecision = useCallback((status: 'approved' | 'rejected' | 'duplicate') => {
    if (!activeItem) return

    // Commit previous staged decision
    if (stagedRef.current) {
      decisionMutation.mutate({
        mediaId: stagedRef.current.item.media_id,
        payload: stagedRef.current.payload
      })
    }

    // Stage current decision
    stagedRef.current = {
      item: activeItem,
      payload: {
        status,
        final_tags: activeItem.tags || [],
        final_primary_folder: status === 'approved' ? (activeItem.suggested_primary_folder || 'Approved') : undefined,
      }
    }
    
    setShowUndo(true)

    // Optimistically update: remove item from queue
    queryClient.setQueryData(['review-queue', eventId], (oldData: any) => {
      if (!oldData) return oldData
      return {
        ...oldData,
        data: oldData.data.filter((item: ReviewQueueItem) => item.media_id !== activeItem.media_id)
      }
    })
  }, [activeItem, decisionMutation, eventId, queryClient])

  const handleUndo = useCallback(() => {
    if (stagedRef.current) {
      const restoredItem = stagedRef.current.item
      stagedRef.current = null
      setShowUndo(false)

      queryClient.setQueryData(['review-queue', eventId], (oldData: any) => {
        if (!oldData) return oldData
        const newData = [...oldData.data]
        newData.splice(activeIndex, 0, restoredItem)
        return { ...oldData, data: newData }
      })
    }
  }, [activeIndex, eventId, queryClient])

  const resumeMutation = useMutation({
    mutationFn: (jobId: string) => resumeJob(jobId),
    onSuccess: () => {
      refetchJobs()
      navigate(`/events/${eventId}`)
    }
  })


  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'z' || e.key === 'Z')) {
        e.preventDefault()
        handleUndo()
        return
      }

      if (!activeItem || decisionMutation.isPending) return
      
      if (e.key === 'ArrowRight') {
        setActiveIndex(prev => Math.min(prev + 1, queue.length - 1))
      } else if (e.key === 'ArrowLeft') {
        setActiveIndex(prev => Math.max(prev - 1, 0))
      } else if (e.key === 'a' || e.key === 'A') {
        handleDecision('approved')
      } else if (e.key === 'r' || e.key === 'R') {
        handleDecision('rejected')
      } else if (e.key === 'f' || e.key === 'F') {
        handleDecision('duplicate')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeItem, queue.length, decisionMutation.isPending, handleDecision, handleUndo])

  if (isQueueLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="size-6 animate-spin text-primary" />
      </div>
    )
  }

  if (isQueueError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2">
        <AlertCircle className="size-8 text-danger" />
        <h2 className="text-xl font-semibold text-foreground">Queue Unavailable</h2>
        <p className="text-sm text-muted-foreground">Failed to load the review queue. The server may be unreachable.</p>
        <button onClick={() => navigate(`/events/${eventId}`)} className="mt-4 text-sm text-primary hover:underline">
          Back to Event Detail
        </button>
      </div>
    )
  }

  if (queue.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
        <div className="flex size-16 items-center justify-center rounded-full bg-surface text-muted-foreground">
          <Check className="size-8" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-foreground">Review Complete</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            There are no more items needing review in this event.
          </p>
        </div>
        
        {waitingJob && (
          <div className="mt-6 rounded-md border border-border bg-card p-6 shadow-sm">
            <h3 className="font-medium text-foreground">Ready to resume pipeline?</h3>
            <p className="mt-1 text-sm text-muted-foreground mb-4">
              Job {waitingJob.id.substring(0, 8)} is paused waiting for your review.
            </p>
            <button
              onClick={() => resumeMutation.mutate(waitingJob.id)}
              disabled={resumeMutation.isPending}
              className="flex w-full items-center justify-center gap-2 rounded-sm bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {resumeMutation.isPending ? <Loader2 className="size-4 animate-spin" /> : <PlayCircle className="size-4" />}
              Resume Processing
            </button>
          </div>
        )}

        {!waitingJob && (
          <button
            onClick={() => navigate(`/events/${eventId}`)}
            className="mt-2 text-sm text-primary hover:underline"
          >
            Back to Event Detail
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card px-4">
        <div>
          <span className="mono-label text-muted-foreground">Queue Progress</span>
          <div className="text-sm font-medium text-foreground">
            {queue.length} items remaining
          </div>
        </div>
        <div className="flex items-center gap-4">
          {showUndo && (
            <button
              onClick={handleUndo}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mono-label"
            >
              <Undo2 className="size-3.5" />
              Undo (⌘Z)
            </button>
          )}
          <StatusChip tone="warn" pulse>Review Required</StatusChip>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Left: Thumbnail Strip */}
        <div className="flex h-24 shrink-0 gap-2 border-b border-border bg-surface p-2 overflow-x-auto lg:w-48 lg:h-auto lg:flex-col lg:border-b-0 lg:border-r overflow-y-auto">
          {queue.map((item, idx) => (
            <button
              key={item.media_id}
              onClick={() => setActiveIndex(idx)}
              className={cn(
                "relative aspect-square h-full shrink-0 overflow-hidden rounded-sm border-2 transition-colors lg:h-auto lg:w-full",
                idx === activeIndex ? "border-primary" : "border-transparent hover:border-border"
              )}
            >
              <img
                src={item.thumbnail_url.startsWith('http') ? item.thumbnail_url : `${import.meta.env.VITE_API_BASE_URL || '/api'}${item.thumbnail_url}`}
                alt="thumbnail"
                className="h-full w-full object-cover"
                loading="lazy"
              />
              {item.is_duplicate && (
                <div className="absolute right-1 top-1 rounded-full bg-danger/80 p-0.5 text-danger-foreground">
                  <AlertCircle className="size-3" />
                </div>
              )}
            </button>
          ))}
        </div>

        {/* Middle: Preview & Actions */}
        <div className="flex min-w-0 flex-1 flex-col bg-background">
          <div className="relative flex min-h-0 flex-1 items-center justify-center p-4">
            {activeItem && (
              <img
                src={activeItem.thumbnail_url.startsWith('http') ? activeItem.thumbnail_url : `${import.meta.env.VITE_API_BASE_URL || '/api'}${activeItem.thumbnail_url}`}
                alt="preview"
                className="max-h-full max-w-full rounded-md object-contain shadow-lg"
              />
            )}

            {/* Nav Overlays */}
            <button
              onClick={() => setActiveIndex(prev => Math.max(prev - 1, 0))}
              disabled={activeIndex === 0}
              className="absolute left-4 top-1/2 -translate-y-1/2 rounded-full bg-surface/50 p-2 text-foreground backdrop-blur-sm transition-colors hover:bg-surface disabled:opacity-30"
            >
              <ChevronLeft className="size-6" />
            </button>
            <button
              onClick={() => setActiveIndex(prev => Math.min(prev + 1, queue.length - 1))}
              disabled={activeIndex === queue.length - 1}
              className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full bg-surface/50 p-2 text-foreground backdrop-blur-sm transition-colors hover:bg-surface disabled:opacity-30"
            >
              <ChevronRight className="size-6" />
            </button>
          </div>

          <div className="flex shrink-0 items-center justify-center gap-4 border-t border-border bg-card p-4">
            <button
              onClick={() => handleDecision('rejected')}
              disabled={decisionMutation.isPending}
              className="group flex flex-col items-center gap-1 text-muted-foreground hover:text-danger disabled:opacity-50"
            >
              <div className="flex size-12 items-center justify-center rounded-full border border-border bg-surface transition-colors group-hover:border-danger/50 group-hover:bg-danger/10">
                <X className="size-5" />
              </div>
              <span className="mono-label">Reject (R)</span>
            </button>

            <button
              onClick={() => handleDecision('approved')}
              disabled={decisionMutation.isPending}
              className="group flex flex-col items-center gap-1 text-muted-foreground hover:text-ok disabled:opacity-50"
            >
              <div className="flex size-14 items-center justify-center rounded-full border border-border bg-surface transition-colors group-hover:border-ok/50 group-hover:bg-ok/10">
                {decisionMutation.isPending && decisionMutation.variables?.payload.status === 'approved' ? (
                  <Loader2 className="size-6 animate-spin text-ok" />
                ) : (
                  <Check className="size-6" />
                )}
              </div>
              <span className="mono-label font-bold text-foreground">Approve (A)</span>
            </button>

            <button
              onClick={() => handleDecision('duplicate')}
              disabled={decisionMutation.isPending}
              className="group flex flex-col items-center gap-1 text-muted-foreground hover:text-warn disabled:opacity-50"
            >
              <div className="flex size-12 items-center justify-center rounded-full border border-border bg-surface transition-colors group-hover:border-warn/50 group-hover:bg-warn/10">
                <Flag className="size-5" />
              </div>
              <span className="mono-label">Flag (F)</span>
            </button>
          </div>
        </div>

        {/* Right: Inspector */}
        <div className="flex w-full shrink-0 flex-col border-t border-border bg-card lg:w-72 lg:border-l lg:border-t-0">
          <div className="border-b border-border p-4">
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Info className="size-4 text-muted-foreground" />
              Inspector
            </h3>
          </div>
          
          {activeItem && (
            <div className="flex flex-col gap-6 p-4">
              <div>
                <span className="mono-label text-muted-foreground">Review Reasons</span>
                <div className="mt-2 flex flex-wrap gap-2">
                  {activeItem.review_reasons.length > 0 ? (
                    activeItem.review_reasons.map((r, i) => (
                      <StatusChip key={i} tone="warn">{r}</StatusChip>
                    ))
                  ) : (
                    <span className="text-sm text-foreground">Manual review</span>
                  )}
                </div>
              </div>

              <div>
                <span className="mono-label text-muted-foreground">Quality Score</span>
                <div className="mt-1 text-sm text-foreground capitalize">
                  {activeItem.quality_label || 'Unknown'}
                </div>
              </div>

              {activeItem.is_duplicate && (
                <div className="rounded-sm border border-danger/20 bg-danger/5 p-3">
                  <span className="mono-label text-danger flex items-center gap-1">
                    <AlertCircle className="size-3" />
                    Duplicate Detected
                  </span>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Matches group {activeItem.duplicate_group_id?.substring(0, 8)}.
                  </p>
                </div>
              )}

              <div>
                <span className="mono-label text-muted-foreground">Suggested Folders</span>
                <div className="mt-1 flex flex-col gap-1 text-sm text-foreground">
                  <p>Primary: {activeItem.suggested_primary_folder || '--'}</p>
                  <p>Sub: {activeItem.suggested_sub_folder || '--'}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
