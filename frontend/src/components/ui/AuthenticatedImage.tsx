import { useEffect, useState } from 'react'
import type { ImgHTMLAttributes } from 'react'
import { clearAdminToken, dispatchAuthLocked, getAdminToken } from '@/lib/auth'
import { resolveApiUrl } from '@/api/client'

type AuthenticatedImageProps = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'> & {
  src: string
}

export function AuthenticatedImage({ src, alt, ...props }: AuthenticatedImageProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    let nextObjectUrl: string | null = null
    const controller = new AbortController()

    async function loadImage() {
      setObjectUrl(null)
      const token = getAdminToken()
      const response = await fetch(resolveApiUrl(src), {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        signal: controller.signal,
      })

      if (response.status === 401) {
        clearAdminToken()
        dispatchAuthLocked()
      }

      if (!response.ok) {
        throw new Error(`Image request failed with status ${response.status}`)
      }

      const blob = await response.blob()
      nextObjectUrl = URL.createObjectURL(blob)
      if (isMounted) {
        setObjectUrl(nextObjectUrl)
      } else {
        URL.revokeObjectURL(nextObjectUrl)
      }
    }

    loadImage().catch(() => {
      if (isMounted) {
        setObjectUrl(null)
      }
    })

    return () => {
      isMounted = false
      controller.abort()
      if (nextObjectUrl) {
        URL.revokeObjectURL(nextObjectUrl)
      }
    }
  }, [src])

  return <img src={objectUrl ?? undefined} alt={alt} {...props} />
}
