import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Lock, ArrowRight, ShieldAlert, KeyRound, Loader2 } from 'lucide-react'
import { setAdminToken, clearAdminToken } from '@/lib/auth'
import { getEvents } from '@/api/events'
import { parseApiError } from '@/api/client'

interface AdminUnlockProps {
  onUnlock: () => void
}

export function AdminUnlock({ onUnlock }: AdminUnlockProps) {
  const [token, setToken] = useState('')
  const [remember, setRemember] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token.trim()) return

    setIsLoading(true)
    setError(null)

    // Optimistically set the token to test it
    setAdminToken(token, remember)

    try {
      // Validate by calling a lightweight private endpoint
      await getEvents()
      // If we succeed, the token is valid
      onUnlock()
    } catch (err: unknown) {
      const apiError = parseApiError(err)
      if (apiError.status === 401) {
        clearAdminToken()
        setError('Invalid admin token. Please try again.')
      } else {
        setError(
          apiError.status === 0
            ? 'Could not reach the backend. Check that it is running.'
            : 'Token accepted, but the backend could not load the dashboard. Check database/storage services.'
        )
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] rounded-full bg-primary/5 blur-[120px]" />
        <div className="absolute top-[60%] -right-[10%] w-[40%] h-[60%] rounded-full bg-primary/5 blur-[120px]" />
      </div>

      <div className="z-10 w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto mb-6 flex size-16 items-center justify-center rounded-2xl bg-surface border border-border shadow-sm">
            <Lock className="size-8 text-primary" strokeWidth={1.5} />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Admin Access
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Enter your admin token to unlock the dashboard.
          </p>
        </div>

        <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
          <form onSubmit={handleUnlock} className="space-y-6">
            <div className="space-y-2">
              <label htmlFor="token" className="text-sm font-medium text-foreground">
                Admin Token
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                  <KeyRound className="size-4 text-muted-foreground" />
                </div>
                <input
                  id="token"
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Enter secure token..."
                  className="flex h-11 w-full rounded-md border border-border bg-background px-3 py-2 pl-10 text-sm placeholder:text-muted-foreground focus:border-primary/60 focus:outline-none focus:ring-1 focus:ring-primary/60 transition-colors"
                  autoFocus
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive border border-destructive/20">
                <ShieldAlert className="size-4 shrink-0" />
                <p>{error}</p>
              </div>
            )}

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="remember"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="h-4 w-4 rounded border-border text-primary focus:ring-primary/60 bg-background"
              />
              <label
                htmlFor="remember"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-muted-foreground"
              >
                Remember this device
              </label>
            </div>

            <button
              type="submit"
              disabled={isLoading || !token.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:pointer-events-none"
            >
              {isLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <>
                  Unlock Dashboard
                  <ArrowRight className="size-4" />
                </>
              )}
            </button>
          </form>
        </div>

        <div className="text-center">
          <Link
            to="/landing"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground inline-flex items-center gap-1.5"
          >
            <ArrowRight className="size-3 rotate-180" />
            Return to Landing
          </Link>
        </div>
      </div>
    </div>
  )
}
