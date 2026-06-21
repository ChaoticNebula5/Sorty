import { useEffect, useState } from 'react'
import { getAdminToken } from '@/lib/auth'
import { AdminUnlock } from './AdminUnlock'

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const [isLocked, setIsLocked] = useState(!getAdminToken())

  useEffect(() => {
    const handleAuthLocked = () => {
      setIsLocked(true)
    }

    // Check on mount in case it was cleared elsewhere
    if (!getAdminToken()) {
      setIsLocked(true)
    }

    window.addEventListener('sorty-admin-locked', handleAuthLocked)
    return () => {
      window.removeEventListener('sorty-admin-locked', handleAuthLocked)
    }
  }, [])

  const handleUnlock = () => {
    setIsLocked(false)
  }

  if (isLocked) {
    return <AdminUnlock onUnlock={handleUnlock} />
  }

  return <>{children}</>
}
