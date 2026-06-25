import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { queryKeys } from '@/app/query-client'
import { DecisionBadge } from '@/components/prediction-result/DecisionBadge'
import { routes } from '@/config/routes'
import { datasetsApi } from '@/features/datasets/api'
import { modelApi } from '@/features/model/api'
import { predictionsApi, type HistoryFilters } from '@/features/predictions/api'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/cn'

const SPLIT_OPTIONS = ['train', 'val', 'test']

export function PredictionHistoryPage() {
  const { t } = useTranslation()
  const [datasetId, setDatasetId] = useState('')
  const [split, setSplit] = useState('')
  const [predictedClass, setPredictedClass] = useState('')
  const [correctness, setCorrectness] = useState('')

  const datasetsQuery = useQuery({
    queryKey: ['datasets', 'list'],
    queryFn: () => datasetsApi.list(),
  })
  const modelQuery = useQuery({ queryKey: queryKeys.modelActive, queryFn: modelApi.active })

  const filters: HistoryFilters = {
    datasetId: datasetId || undefined,
    split: split || undefined,
    predictedClass: predictedClass || undefined,
    isCorrect: correctness === '' ? undefined : correctness === 'correct',
  }

  const historyQuery = useQuery({
    queryKey: queryKeys.predictionsHistory(filters),
    queryFn: () => predictionsApi.history(filters),
  })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 pb-24">
      <div>
        <h1 className="text-h1 text-text-primary">{t('analysis.history.title')}</h1>
        <p className="mt-2 text-base text-text-secondary">{t('analysis.history.intro')}</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('analysis.history.filters.dataset')}
          <select
            value={datasetId}
            onChange={(event) => setDatasetId(event.target.value)}
            className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
          >
            <option value="">{t('analysis.history.filters.allDatasets')}</option>
            {datasetsQuery.data?.items.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('analysis.history.filters.split')}
          <select
            value={split}
            onChange={(event) => setSplit(event.target.value)}
            className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
          >
            <option value="">{t('analysis.history.filters.allSplits')}</option>
            {SPLIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('analysis.history.filters.predictedClass')}
          <select
            value={predictedClass}
            onChange={(event) => setPredictedClass(event.target.value)}
            className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
          >
            <option value="">{t('analysis.history.filters.allClasses')}</option>
            {modelQuery.data?.class_names.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('analysis.history.filters.correctness')}
          <select
            value={correctness}
            onChange={(event) => setCorrectness(event.target.value)}
            className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
          >
            <option value="">{t('analysis.history.filters.any')}</option>
            <option value="correct">{t('analysis.history.filters.correct')}</option>
            <option value="incorrect">{t('analysis.history.filters.incorrect')}</option>
          </select>
        </label>
      </div>

      {historyQuery.isLoading && (
        <p className="text-base text-text-muted">{t('analysis.history.loading')}</p>
      )}

      {historyQuery.isError && (
        <p className="text-base text-danger">
          {historyQuery.error instanceof ApiError
            ? historyQuery.error.message
            : t('analysis.history.error')}
        </p>
      )}

      {historyQuery.data && historyQuery.data.items.length === 0 && (
        <div className="flex flex-col items-start gap-4 rounded-(--radius-lg) border border-border bg-surface p-6">
          <p className="text-base text-text-secondary">{t('analysis.history.empty')}</p>
          <Link
            to={routes.datasets}
            className="inline-flex h-13 items-center justify-center rounded-(--radius-md) bg-primary px-6 text-base font-medium text-text-inverse hover:bg-primary-hover"
          >
            {t('analysis.history.emptyCta')}
          </Link>
        </div>
      )}

      {historyQuery.data && historyQuery.data.items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {historyQuery.data.items.map((item) => (
            <li key={item.id}>
              <Link
                to={routes.predictionDetail(item.id)}
                className="flex flex-col gap-2 rounded-(--radius-lg) border border-border bg-surface p-4 hover:border-primary sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex flex-col gap-1">
                  <span className="text-base font-medium text-text-primary">
                    {item.predicted_class ?? t('analysis.history.unknownClass')}
                  </span>
                  <span className="text-sm text-text-muted">{formatDateTime(item.created_at)}</span>
                </div>
                <div className="flex items-center gap-2">
                  {item.dataset_id ? (
                    <span
                      className={cn(
                        'rounded-full px-3 py-1 text-xs font-semibold',
                        item.is_correct
                          ? 'bg-positive-soft text-positive'
                          : 'bg-warning-soft text-warning',
                      )}
                    >
                      {t(
                        item.is_correct
                          ? 'analysis.history.matchCorrect'
                          : 'analysis.history.matchIncorrect',
                      )}
                    </span>
                  ) : (
                    <span className="rounded-full bg-surface-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
                      {t('analysis.history.legacyTag')}
                    </span>
                  )}
                  <DecisionBadge decision={item.decision} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
