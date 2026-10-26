import { useEffect, useState } from 'react'
import { clearAdminToken, getAdminToken } from '@/lib/auth'
import { getEvents, isEventsListResponse } from '@/api/events'
import { AdminUnlock } from './AdminUnlock'
import { Loader2 } from 'lucide-react'

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const [isLocked, setIsLocked] = useState(true)
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    let isMounted = true

    const handleAuthLocked = () => {
      setIsLocked(true)
      setIsChecking(false)
    }

    async function validateStoredToken() {
      if (!getAdminToken()) {
        if (isMounted) {
          setIsLocked(true)
          setIsChecking(false)
        }
        return
      }

      try {
        const response = await getEvents()
        if (!isEventsListResponse(response)) {
          throw new Error('Invalid admin API response.')
        }
        if (isMounted) {
          setIsLocked(false)
        }
      } catch {
        clearAdminToken()
        if (isMounted) {
          setIsLocked(true)
        }
      } finally {
        if (isMounted) {
          setIsChecking(false)
        }
      }
    }

    validateStoredToken()

    window.addEventListener('sorty-admin-locked', handleAuthLocked)
    return () => {
      isMounted = false
      window.removeEventListener('sorty-admin-locked', handleAuthLocked)
    }
  }, [])

  const handleUnlock = () => {
    setIsLocked(false)
    setIsChecking(false)
  }

  if (isChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-6 animate-spin text-primary" />
      </div>
    )
  }

  if (isLocked) {
    return <AdminUnlock onUnlock={handleUnlock} />
  }

  return <>{children}</>
}
