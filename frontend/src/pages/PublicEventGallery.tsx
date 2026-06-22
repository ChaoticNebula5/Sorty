
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getPublicEvent, getPublicEventMedia } from '@/api/events'
import { Loader2, AlertCircle, ImageIcon } from 'lucide-react'

export function PublicEventGallery() {
  const { publicSlug } = useParams<{ publicSlug: string }>()

  const { data: eventData, isLoading: isEventLoading, isError: isEventError } = useQuery({
    queryKey: ['publicEvent', publicSlug],
    queryFn: () => getPublicEvent(publicSlug!),
    enabled: !!publicSlug,
  })

  const { data: mediaData, isLoading: isMediaLoading } = useQuery({
    queryKey: ['publicEventMedia', publicSlug],
    queryFn: () => getPublicEventMedia(publicSlug!),
    enabled: !!publicSlug,
  })

  if (isEventError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background text-center p-6">
        <AlertCircle className="size-10 text-muted-foreground mb-4" />
        <h1 className="text-2xl font-semibold text-foreground">Public event not found</h1>
        <p className="mt-2 text-muted-foreground">The event you're looking for doesn't exist or isn't public.</p>
      </div>
    )
  }

  if (isEventLoading || !eventData?.data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    )
  }

  const event = eventData.data
  const mediaItems = mediaData?.data || []

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-card px-6 py-8 sm:px-12 sm:py-12">
        <div className="mx-auto max-w-6xl">
          <div className="mono-label text-primary">{event.event_type}</div>
          <h1 className="mt-2 text-3xl sm:text-4xl font-semibold tracking-tight text-foreground">
            {event.name}
          </h1>
          {event.description && (
            <p className="mt-3 text-lg text-muted-foreground max-w-2xl">
              {event.description}
            </p>
          )}
          <div className="mt-4 text-sm text-muted-foreground">
            Published {new Date(event.published_at).toLocaleDateString()}
          </div>
        </div>
      </div>

      {/* Gallery */}
      <div className="mx-auto max-w-6xl px-6 py-8 sm:px-12">
        {isMediaLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="size-6 animate-spin text-primary" />
          </div>
        ) : mediaItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center rounded-lg border border-dashed border-border bg-surface">
            <ImageIcon className="size-10 text-muted-foreground mb-3 opacity-50" />
            <h3 className="text-lg font-medium text-foreground">No public media yet</h3>
            <p className="text-sm text-muted-foreground mt-1">Check back later for updates to this event.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {mediaItems.map((item) => (
              <div key={item.media_id} className="group relative aspect-square overflow-hidden rounded-md bg-surface border border-border">
                <img
                  src={item.thumbnail_url}
                  alt={item.tags.join(', ') || 'Event media'}
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                  loading="lazy"
                />
                
                {/* Labels overlay */}
                <div className="absolute top-2 left-2 flex flex-col gap-1">
                  {item.quality_label && (
                    <span className="inline-flex items-center rounded-full bg-black/60 px-2 py-0.5 text-xs font-medium text-white backdrop-blur-sm">
                      {item.quality_label}
                    </span>
                  )}
                </div>
                
                {/* Tags overlay on hover */}
                {item.tags && item.tags.length > 0 && (
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-3 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                    <div className="flex flex-wrap gap-1">
                      {item.tags.slice(0, 3).map(tag => (
                        <span key={tag} className="text-[10px] font-medium text-white bg-white/20 rounded-sm px-1.5 py-0.5 backdrop-blur-sm">
                          {tag}
                        </span>
                      ))}
                      {item.tags.length > 3 && (
                        <span className="text-[10px] font-medium text-white/80">+{item.tags.length - 3}</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
