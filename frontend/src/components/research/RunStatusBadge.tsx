import { useTranslation } from 'react-i18next'

import type { RunStatus } from '@/features/research/api'
import { cn } from '@/lib/cn'

const STATUS_STYLE: Record<RunStatus, string> = {
  pending: 'bg-surface-subtle text-text-secondary',
  running: 'bg-primary-soft text-primary',
  completed: 'bg-success-soft text-success',
  failed: 'bg-danger-soft text-danger',
  cancelled: 'bg-surface-subtle text-text-muted',
  invalidated: 'bg-danger-soft text-danger',
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold',
        STATUS_STYLE[status],
      )}
    >
      {t(`research.status.${status}`)}
    </span>
  )
}
