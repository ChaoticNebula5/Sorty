import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createEvent } from '@/api/events'
import { Loader2 } from 'lucide-react'

export function CreateEvent() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  const [name, setName] = useState('')
  const [eventType, setEventType] = useState('conference')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createEvent,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      navigate(`/events/${data.data.id}`)
    },
    onError: (err: any) => {
      setError(err.message || 'Failed to create event')
    }
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    mutation.mutate({ name, event_type: eventType, description })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-6 py-5">
        <div className="mono-label text-muted-foreground">Workspace / New</div>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-foreground">
          Create Event
        </h1>
      </div>

      <div className="p-6 max-w-xl">
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {error && (
            <div className="rounded-sm bg-danger/10 border border-danger/30 p-3 text-sm text-danger">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label htmlFor="name" className="text-sm font-medium text-foreground">
              Event Name
            </label>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-10 w-full rounded-sm border border-border bg-surface px-3 text-sm text-foreground focus:border-primary/60 focus:outline-none"
              placeholder="e.g. Global Tech Summit 2026"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="type" className="text-sm font-medium text-foreground">
              Event Type
            </label>
            <select
              id="type"
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              className="h-10 w-full rounded-sm border border-border bg-surface px-3 text-sm text-foreground focus:border-primary/60 focus:outline-none"
            >
              <option value="conference">Conference</option>
              <option value="gala">Gala / Party</option>
              <option value="hackathon">Hackathon</option>
              <option value="press">Press Event</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="desc" className="text-sm font-medium text-foreground">
              Description <span className="text-muted-foreground font-normal">(Optional)</span>
            </label>
            <textarea
              id="desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary/60 focus:outline-none"
              placeholder="Internal notes or context"
            />
          </div>

          <div className="mt-2 flex gap-3">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="flex items-center gap-2 rounded-sm border border-border bg-surface px-4 py-2 text-sm text-foreground transition-colors hover:bg-elevated"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending || !name}
              className="flex items-center gap-2 rounded-sm bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {mutation.isPending ? <Loader2 className="size-4 animate-spin" /> : 'Create Event'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
