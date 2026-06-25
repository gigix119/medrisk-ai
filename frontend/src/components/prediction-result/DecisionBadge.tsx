import { AlertTriangle, CheckCircle2, HelpCircle } from 'lucide-react'
import type { ComponentType } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/cn'

interface DecisionConfig {
  icon: ComponentType<{ size?: number; 'aria-hidden'?: boolean }>
  colorClass: string
  bgClass: string
  labelKey: string
}

const DECISION_CONFIG: Record<string, DecisionConfig> = {
  negative: {
    icon: CheckCircle2,
    colorClass: 'text-negative',
    bgClass: 'bg-negative-soft',
    labelKey: 'analysis.result.decision.negative',
  },
  positive: {
    icon: AlertTriangle,
    colorClass: 'text-positive',
    bgClass: 'bg-positive-soft',
    labelKey: 'analysis.result.decision.positive',
  },
  review_required: {
    icon: HelpCircle,
    colorClass: 'text-review',
    bgClass: 'bg-review-soft',
    labelKey: 'analysis.result.decision.review',
  },
}

export function DecisionBadge({ decision }: { decision: string | null }) {
  const { t } = useTranslation()
  const config = decision ? DECISION_CONFIG[decision] : undefined

  if (!config) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-surface-subtle px-4 py-2 text-sm font-semibold text-text-secondary">
        {t('analysis.result.decision.unknown')}
      </span>
    )
  }

  const Icon = config.icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold',
        config.colorClass,
        config.bgClass,
      )}
    >
      <Icon aria-hidden size={18} />
      {t(config.labelKey)}
    </span>
  )
}
