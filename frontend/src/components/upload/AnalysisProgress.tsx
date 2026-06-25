import { CheckCircle2, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/cn'

const STAGE_KEYS = [
  'validating',
  'uploading',
  'preparing',
  'running',
  'explaining',
  'finalizing',
] as const

const STAGE_INTERVAL_MS = 900

/** The backend call is a single synchronous request, so there is no real progress
 * percentage to report - this cycles through named stages on a cosmetic timer rather than
 * faking a percentage, and simply holds on the last stage until the request settles. */
export function AnalysisProgress() {
  const { t } = useTranslation()
  const [stageIndex, setStageIndex] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setStageIndex((index) => Math.min(index + 1, STAGE_KEYS.length - 1))
    }, STAGE_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [])

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-6"
    >
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-subtle">
        <div className="h-full w-1/3 animate-pulse rounded-full bg-primary" />
      </div>
      <ul className="flex flex-col gap-2">
        {STAGE_KEYS.map((key, index) => (
          <li
            key={key}
            className={cn(
              'flex items-center gap-2 text-sm',
              index <= stageIndex ? 'font-medium text-text-primary' : 'text-text-muted',
            )}
          >
            {index < stageIndex ? (
              <CheckCircle2 aria-hidden size={16} className="text-negative" />
            ) : index === stageIndex ? (
              <Loader2 aria-hidden size={16} className="animate-spin text-primary" />
            ) : (
              <span aria-hidden className="inline-block h-4 w-4" />
            )}
            {t(`analysis.progress.${key}`)}
          </li>
        ))}
      </ul>
    </div>
  )
}
