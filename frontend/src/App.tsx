import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { LandingPage } from '@/pages/LandingPage'
import { EventsLibrary } from '@/pages/EventsLibrary'
import { CreateEvent } from '@/pages/CreateEvent'
import { EventDetail } from '@/pages/EventDetail'
import { ReviewQueue } from '@/pages/ReviewQueue'
import { EventSearch } from '@/pages/EventSearch'
import { PublicEventGallery } from '@/pages/PublicEventGallery'

import { useQuery } from '@tanstack/react-query'
import { getEvents } from '@/api/events'
import { Plus, ArrowRight } from 'lucide-react'

function EventRequiredState({ title, description }: { title: string, description: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['events'],
    queryFn: getEvents,
  })

  const events = data?.data || []

  return (
    <div className="flex h-full flex-col items-center justify-center p-6 text-center">
      <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
      <p className="mt-2 text-muted-foreground max-w-md">{description}</p>
      
      {!isLoading && (
        <div className="mt-8 flex gap-4">
          {events.length === 0 ? (
            <Link
              to="/events/new"
              className="flex items-center gap-2 rounded-sm bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              <Plus className="size-4" />
              Create your first Event
            </Link>
          ) : (
            <Link
              to="/"
              className="flex items-center gap-2 rounded-sm bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              Select Event from Library
              <ArrowRight className="size-4" />
            </Link>
          )}
        </div>
      )}
    </div>
  )
}

import { AdminGuard } from '@/components/auth/AdminGuard'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/landing" element={<LandingPage />} />
        <Route path="/public/events/:publicSlug" element={<PublicEventGallery />} />
        <Route element={<AdminGuard><AppShell /></AdminGuard>}>
          <Route path="/" element={<EventsLibrary />} />
          <Route path="/events/new" element={<CreateEvent />} />
          <Route path="/events/:eventId" element={<EventDetail />} />
          <Route path="/events/:eventId/review" element={<ReviewQueue />} />
          <Route path="/events/:eventId/search" element={<EventSearch />} />
          <Route path="/processing" element={<EventRequiredState title="Upload & Processing" description="Uploads are tied to specific events. Please select an event to upload media or monitor processing jobs." />} />
          <Route path="/review" element={<EventRequiredState title="Review Queue" description="The human review queue is scoped to an event. Please select an event to review uncertain or flagged media." />} />
          <Route path="/search" element={<EventRequiredState title="Search & Export" description="Search and export are scoped to specific events. Select an event to generate ZIP packs or search media." />} />
          <Route path="/archive" element={<EventRequiredState title="Archive" description="The archive contains cold-storage events. Select an event from the library to archive it." />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
