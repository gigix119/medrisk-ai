import { useTranslation } from 'react-i18next'

import type { ClassProbability } from '@/features/predictions/result-view-model'
import { cn } from '@/lib/cn'
import { formatPercent } from '@/lib/format'

export function ProbabilityBars({ probabilities }: { probabilities: ClassProbability[] }) {
  const { t } = useTranslation()

  return (
    <ul className="flex flex-col gap-4">
      {probabilities.map((item) => (
        <li key={item.label}>
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span
              className={cn(
                'text-base font-medium',
                item.isPredicted ? 'text-text-primary' : 'text-text-secondary',
              )}
            >
              {item.label}
              {item.isPredicted && (
                <span className="ml-2 text-xs font-semibold text-primary">
                  {t('analysis.result.predictedTag')}
                </span>
              )}
            </span>
            <span className="text-base font-semibold text-text-primary">
              {formatPercent(item.probability)}
            </span>
          </div>
          <div
            role="img"
            aria-label={`${item.label}: ${formatPercent(item.probability)}`}
            className="h-3 w-full overflow-hidden rounded-full bg-surface-subtle"
          >
            <div
              className={cn(
                'h-full rounded-full transition-[width]',
                item.isPredicted ? 'bg-primary' : 'bg-border-strong',
              )}
              style={{ width: `${Math.round(item.probability * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
