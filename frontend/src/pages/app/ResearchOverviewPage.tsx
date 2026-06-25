import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { ResultClassificationBadge } from '@/components/research/ResultClassificationBadge'
import { RunStatusBadge } from '@/components/research/RunStatusBadge'
import { Button } from '@/components/ui/Button'
import { routes } from '@/config/routes'
import { datasetsApi } from '@/features/datasets/api'
import { researchApi, type RunStatus } from '@/features/research/api'
import { formatDateTime, formatMetricValue } from '@/lib/format'

const PAGE_SIZE = 20
const STATUS_OPTIONS: RunStatus[] = [
  'pending',
  'running',
  'completed',
  'failed',
  'cancelled',
  'invalidated',
]

export function ResearchOverviewPage() {
  const { t } = useTranslation()
  const [datasetId, setDatasetId] = useState('')
  const [status, setStatus] = useState<RunStatus | ''>('')
  const [offset, setOffset] = useState(0)

  const datasetsQuery = useQuery({
    queryKey: ['datasets', 'list'],
    queryFn: () => datasetsApi.list(),
  })
  const datasetNameById = new Map(
    (datasetsQuery.data?.items ?? []).map((dataset) => [dataset.id, dataset.name]),
  )

  const evaluationsQuery = useQuery({
    queryKey: ['research', 'evaluations', datasetId, status, offset],
    queryFn: () =>
      researchApi.listEvaluations({
        datasetId: datasetId || undefined,
        status: status || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
  })

  const total = evaluationsQuery.data?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + PAGE_SIZE, total)

  function resetAndSet(setter: () => void) {
    setter()
    setOffset(0)
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 pb-24">
      <div>
        <h1 className="text-h1 text-text-primary">{t('research.overview.title')}</h1>
        <p className="mt-2 text-base text-text-secondary">{t('research.overview.intro')}</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('research.overview.filters.dataset')}
          <select
            value={datasetId}
            onChange={(event) => resetAndSet(() => setDatasetId(event.target.value))}
            className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
          >
            <option value="">{t('research.overview.filters.allDatasets')}</option>
            {datasetsQuery.data?.items.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('research.overview.filters.status')}
          <select
            value={status}
            onChange={(event) => resetAndSet(() => setStatus(event.target.value as RunStatus | ''))}
            className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
          >
            <option value="">{t('research.overview.filters.allStatuses')}</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(`research.status.${option}`)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {evaluationsQuery.isLoading && (
        <p className="text-base text-text-muted">{t('research.overview.loading')}</p>
      )}

      {evaluationsQuery.isError && (
        <p className="text-base text-danger">
          {evaluationsQuery.error instanceof ApiError
            ? evaluationsQuery.error.message
            : t('research.overview.error')}
        </p>
      )}

      {evaluationsQuery.data && evaluationsQuery.data.items.length === 0 && (
        <p className="text-base text-text-muted">{t('research.overview.empty')}</p>
      )}

      {evaluationsQuery.data && evaluationsQuery.data.items.length > 0 && (
        <>
          <ul className="flex flex-col gap-3">
            {evaluationsQuery.data.items.map((run) => (
              <li key={run.id}>
                <Link
                  to={routes.researchResult(run.id)}
                  className="flex flex-col gap-3 rounded-(--radius-lg) border border-border bg-surface p-4 hover:border-primary"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-base font-semibold text-text-primary">
                      {run.model_id} <span className="text-text-muted">v{run.model_version}</span>
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      <RunStatusBadge status={run.status} />
                      <ResultClassificationBadge classification={run.result_classification} />
                    </div>
                  </div>

                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-text-secondary sm:grid-cols-4">
                    <dt className="font-medium text-text-primary">
                      {t('research.overview.fields.dataset')}
                    </dt>
                    <dd>
                      {run.dataset_id
                        ? (datasetNameById.get(run.dataset_id) ?? run.dataset_id)
                        : '—'}
                    </dd>
                    <dt className="font-medium text-text-primary">
                      {t('research.overview.fields.split')}
                    </dt>
                    <dd>{run.split_name}</dd>
                    <dt className="font-medium text-text-primary">
                      {t('research.overview.fields.primaryMetric')}
                    </dt>
                    <dd>
                      {run.primary_metric_name && run.primary_metric_value != null
                        ? `${run.primary_metric_name.replace(/_/g, ' ')}: ${formatMetricValue(run.primary_metric_value)}`
                        : t('research.overview.fields.noPrimaryMetric')}
                    </dd>
                    <dt className="font-medium text-text-primary">
                      {t('research.overview.fields.created')}
                    </dt>
                    <dd>{formatDateTime(run.created_at)}</dd>
                  </dl>
                </Link>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-text-muted">
              {t('research.overview.pageInfo', { from, to, total })}
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                {t('research.overview.previous')}
              </Button>
              <Button
                variant="secondary"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                {t('research.overview.next')}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
