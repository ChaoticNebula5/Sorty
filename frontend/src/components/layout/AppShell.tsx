import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Archive,
  Bell,
  Search,
  CheckSquare,
  UploadCloud,
  Aperture,
  Library,
  Command,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

const baseNav = [
  { icon: Library, label: 'Events Library', href: '/', end: true },
  { icon: UploadCloud, label: 'Upload & Processing', href: '/processing' },
  { icon: CheckSquare, label: 'Review Queue', href: '/review' },
  { icon: Search, label: 'Search & Export', href: '/search' },
  { icon: Archive, label: 'Archive', href: '/archive' },
]

function Sidebar({ activeEventId }: { activeEventId: string | null }) {
  const nav = baseNav.map(item => {
    if (activeEventId) {
      if (item.label === 'Review Queue') return { ...item, href: `/events/${activeEventId}/review` }
      if (item.label === 'Search & Export') return { ...item, href: `/events/${activeEventId}/search` }
      if (item.label === 'Upload & Processing') return { ...item, href: `/events/${activeEventId}` }
    }
    return item
  })

  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-sidebar">
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <div className="flex size-7 items-center justify-center rounded-sm bg-primary text-primary-foreground">
          <Aperture className="size-4" />
        </div>
        <span className="text-sm font-semibold tracking-tight">Sorty</span>
        <span className="mono-label ml-auto rounded-sm border border-border px-1 py-0.5 text-muted-foreground">
          v2.4
        </span>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 p-2 overflow-y-auto overflow-x-hidden">
        <p className="mono-label px-2 pb-1.5 pt-3 text-muted-foreground">
          Workspace
        </p>
        {nav.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.label}
              to={item.href}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-sm px-2 py-1.5 text-sm transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-sidebar-foreground hover:bg-surface hover:text-foreground'
                )
              }
            >
              <Icon className="size-4 shrink-0" strokeWidth={1.75} />
              <span className="truncate">{item.label}</span>
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}

function CommandBar() {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/70 px-4 backdrop-blur-md sticky top-0 z-10">
      <div className="relative flex w-full max-w-xl items-center">
        <Search className="absolute left-3 size-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search events or files..."
          className="h-9 w-full rounded-sm border border-border bg-surface pl-9 pr-20 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/60 focus:outline-none"
        />
        <kbd className="mono-label absolute right-3 flex items-center gap-1 rounded-sm border border-border bg-elevated px-1.5 py-0.5 text-muted-foreground">
          <Command className="size-3" />K
        </kbd>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          className="relative flex size-9 items-center justify-center rounded-sm border border-border bg-surface text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Notifications"
        >
          <Bell className="size-4" />
        </button>
      </div>
    </header>
  )
}

export function AppShell() {
  const location = useLocation()
  const [activeEventId, setActiveEventId] = useState<string | null>(sessionStorage.getItem('activeEventId'))

  useEffect(() => {
    const match = location.pathname.match(/\/events\/([^/]+)/)
    if (match && match[1] && match[1] !== 'new') {
      sessionStorage.setItem('activeEventId', match[1])
      setActiveEventId(match[1])
    }
  }, [location.pathname])

  const nav = baseNav.map(item => {
    if (activeEventId) {
      if (item.label === 'Review Queue') return { ...item, href: `/events/${activeEventId}/review` }
      if (item.label === 'Search & Export') return { ...item, href: `/events/${activeEventId}/search` }
      if (item.label === 'Upload & Processing') return { ...item, href: `/events/${activeEventId}` }
    }
    return item
  })

  return (
    <div className="flex h-screen flex-col md:flex-row overflow-hidden bg-background">
      <Sidebar activeEventId={activeEventId} />
      <div className="flex min-w-0 flex-1 flex-col">
        <CommandBar />
        <main className="min-h-0 flex-1 overflow-y-auto pb-16 md:pb-0">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.15, ease: 'easeOut' }}
              className="h-full"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* Mobile Bottom Nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 flex h-16 items-center justify-around border-t border-border bg-sidebar/80 px-2 backdrop-blur-md pb-safe">
        {nav.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.label}
              to={item.href}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center justify-center gap-1 rounded-sm p-2 text-[10px] transition-colors',
                  isActive
                    ? 'text-primary'
                    : 'text-muted-foreground hover:text-foreground'
                )
              }
            >
              <Icon className="size-5 shrink-0" strokeWidth={1.75} />
              <span className="truncate">{item.label.split(' ')[0]}</span>
            </NavLink>
          )
        })}
      </nav>
    </div>
  )
}
