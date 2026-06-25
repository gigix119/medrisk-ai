import { useTranslation } from 'react-i18next'

import type { ResultClassification } from '@/features/research/api'

/** Deliberately a single neutral style for every classification value - none of them is a
 * "better" or "approved" result than another, they only describe evaluation rigor (e.g.
 * synthetic demonstration vs. held-out test). Color-coding by perceived quality would risk
 * implying a clinical-validity ranking the master spec explicitly forbids. */
export function ResultClassificationBadge({
  classification,
}: {
  classification: ResultClassification
}) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-center rounded-full bg-surface-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
      {t(`research.classification.${classification}`)}
    </span>
  )
}
