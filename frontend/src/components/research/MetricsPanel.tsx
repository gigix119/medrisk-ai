import { Fragment } from 'react'
import { useTranslation } from 'react-i18next'

import type { MetricResult } from '@/features/research/api'
import { formatMetricValue } from '@/lib/format'

/** Every non-"ok" status (e.g. "undefined" for a metric that is mathematically undefined on
 * this split, "unavailable" for one that was never computed) renders its `reason` instead of
 * a value - this panel must never substitute 0 or hide the metric, per the backend's
 * `app.research.domain.metric_shaping` contract. */
export function MetricsPanel({
  metrics,
  counts,
}: {
  metrics: MetricResult[]
  counts: Record<string, number>
}) {
  const { t } = useTranslation()
  const countEntries = Object.entries(counts)

  return (
    <div className="rounded-(--radius-lg) border border-border bg-surface p-5">
      <h2 className="text-h3 text-text-primary">{t('research.result.metrics.title')}</h2>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-sm text-text-secondary">
        {metrics.map((metric) => (
          <Fragment key={metric.name}>
            <dt className="font-medium text-text-primary">{metric.name.replace(/_/g, ' ')}</dt>
            <dd>
              {metric.status === 'ok' && metric.value != null ? (
                formatMetricValue(metric.value)
              ) : (
                <span className="text-text-muted" title={metric.reason ?? undefined}>
                  {t(`research.result.metrics.status.${metric.status}`, {
                    defaultValue: metric.status,
                  })}
                </span>
              )}
            </dd>
          </Fragment>
        ))}
      </dl>

      {countEntries.length > 0 && (
        <>
          <h3 className="mt-5 text-sm font-semibold text-text-primary">
            {t('research.result.metrics.counts')}
          </h3>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm text-text-secondary">
            {countEntries.map(([name, value]) => (
              <Fragment key={name}>
                <dt className="font-medium text-text-primary">{name.replace(/_/g, ' ')}</dt>
                <dd>{value}</dd>
              </Fragment>
            ))}
          </dl>
        </>
      )}
    </div>
  )
}
