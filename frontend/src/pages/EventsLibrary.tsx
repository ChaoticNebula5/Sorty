import { useQuery } from '@tanstack/react-query'
import { Plus, SlidersHorizontal, Loader2 } from 'lucide-react'
import { EventCard } from '@/components/domain/EventCard'
import { getEvents } from '@/api/events'
import { Link } from 'react-router-dom'

export function EventsLibrary() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['events'],
    queryFn: getEvents,
  })

  const events = data?.data || []

  return (
    <div className="flex flex-col">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border px-6 py-5">
        <div>
          <div className="mono-label text-muted-foreground">
            Workspace / Events
          </div>
          <h1 className="mt-1 text-xl font-semibold tracking-tight text-foreground">
            Events Library
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 rounded-sm border border-border bg-surface px-3 py-2 text-sm text-foreground transition-colors hover:bg-elevated">
            <SlidersHorizontal className="size-4 text-muted-foreground" />
            Filters
          </button>
          <Link
            to="/events/new"
            className="flex items-center gap-2 rounded-sm bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Plus className="size-4" />
            New Event
          </Link>
        </div>
      </div>

      {isLoading && (
        <div className="flex h-64 items-center justify-center text-primary">
          <Loader2 className="size-8 animate-spin" />
        </div>
      )}

      {isError && (
        <div className="flex h-64 items-center justify-center text-danger">
          <p>Failed to load events.</p>
        </div>
      )}

      {!isLoading && !isError && events.length === 0 && (
        <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
          <p>No events found.</p>
          <Link to="/events/new" className="text-primary hover:underline text-sm">
            Create your first event
          </Link>
        </div>
      )}

      {/* Media grid */}
      {!isLoading && !isError && events.length > 0 && (
        <div className="grid grid-cols-1 gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {events.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      )}
    </div>
  )
}
