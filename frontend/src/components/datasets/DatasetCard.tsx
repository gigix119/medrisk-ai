import { Database } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { routes } from '@/config/routes'
import type { DatasetRead } from '@/features/datasets/api'

export function DatasetCard({ dataset }: { dataset: DatasetRead }) {
  const { t } = useTranslation()

  return (
    <Link
      to={routes.datasetDetail(dataset.id)}
      className="flex flex-col gap-3 rounded-(--radius-lg) border border-border bg-surface p-5 hover:border-primary"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-text-primary">
          <Database aria-hidden size={20} className="shrink-0 text-primary" />
          <h3 className="text-h3 leading-tight">{dataset.name}</h3>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {dataset.is_synthetic && (
          <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-semibold text-warning">
            {t('datasets.explorer.syntheticBadge')}
          </span>
        )}
        {dataset.is_public && (
          <span className="rounded-full bg-surface-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
            {t('datasets.explorer.publicBadge')}
          </span>
        )}
        <span className="rounded-full bg-surface-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
          v{dataset.version}
        </span>
      </div>

      <p className="text-sm text-text-secondary">{dataset.description}</p>

      <dl className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1 text-sm text-text-secondary">
        <dt className="font-medium text-text-primary">
          {t('datasets.explorer.samplesCount', { count: dataset.sample_count })}
        </dt>
        <dt className="font-medium text-text-primary">
          {t('datasets.explorer.classesCount', { count: dataset.classes.length })}
        </dt>
      </dl>

      <span className="mt-2 text-sm font-semibold text-primary">
        {t('datasets.explorer.viewCta')} →
      </span>
    </Link>
  )
}
