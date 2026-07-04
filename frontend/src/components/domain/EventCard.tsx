import { Link } from 'react-router-dom'
import { ImageIcon } from 'lucide-react'
import { StatusChip } from '@/components/ui/StatusChip'
import type { EventItem } from '@/api/types'

export function EventCard({ event }: { event: EventItem }) {
  // We don't have all the fake stats like 'team' or 'assets', so we show what's available
  // Real stats can be fetched via media-summary if needed, but for listing we keep it simple.

  return (
    <Link
      to={`/events/${event.id}`}
      className="group flex flex-col overflow-hidden rounded-md border border-border bg-card transition-colors hover:border-primary/50"
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-elevated">
        <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-background/10 to-transparent z-10" />
        
        {/* We can use a placeholder cover since we don't have real cover images yet */}
        <div className="absolute inset-0 bg-surface group-hover:scale-105 transition-transform duration-500 flex items-center justify-center">
          <ImageIcon className="size-8 text-muted-foreground/30" />
        </div>

        <div className="absolute left-2.5 top-2.5 z-20">
          <StatusChip tone="info">
            {event.event_type}
          </StatusChip>
        </div>
      </div>

      <div className="flex flex-col gap-3 p-3.5 relative z-20 bg-card">
        <div>
          <h3 className="truncate text-sm font-semibold text-foreground">
            {event.name}
          </h3>
          <p className="mono-label mt-1 text-muted-foreground">
            {new Date(event.created_at).toLocaleDateString()}
          </p>
        </div>
      </div>
    </Link>
  )
}
