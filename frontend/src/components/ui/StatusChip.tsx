import React from 'react'
import { cn } from '@/lib/utils'

export type StatusTone = 'ok' | 'warn' | 'danger' | 'info' | 'muted'

export function StatusChip({
  children,
  tone = 'muted',
  pulse = false,
  className,
}: {
  children: React.ReactNode
  tone?: StatusTone
  pulse?: boolean
  className?: string
}) {
  const tones = {
    ok: 'border-ok/30 bg-ok/10 text-ok',
    warn: 'border-warn/30 bg-warn/10 text-warn',
    danger: 'border-danger/30 bg-danger/10 text-danger',
    info: 'border-info/30 bg-info/10 text-info',
    muted: 'border-border bg-surface text-muted-foreground',
  }

  const dotTones = {
    ok: 'bg-ok',
    warn: 'bg-warn',
    danger: 'bg-danger',
    info: 'bg-info',
    muted: 'bg-muted-foreground',
  }

  return (
    <span
      className={cn(
        'mono-label flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5',
        tones[tone],
        className,
      )}
    >
      <span className="relative flex size-1.5 items-center justify-center">
        {pulse && (
          <span
            className={cn(
              'absolute inline-flex h-full w-full animate-ping rounded-full opacity-75',
              dotTones[tone],
            )}
          />
        )}
        <span
          className={cn('relative inline-flex size-1.5 rounded-full', dotTones[tone])}
        />
      </span>
      {children}
    </span>
  )
}
