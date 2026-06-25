import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { ConfusionMatrixPanel } from '@/components/research/ConfusionMatrixPanel'
import { MetricsPanel } from '@/components/research/MetricsPanel'
import { ResultClassificationBadge } from '@/components/research/ResultClassificationBadge'
import { RunStatusBadge } from '@/components/research/RunStatusBadge'
import { Button } from '@/components/ui/Button'
import { routes } from '@/config/routes'
import { researchApi } from '@/features/research/api'
import { formatDateTime, formatPercent } from '@/lib/format'

const ERRORS_PAGE_SIZE = 10

export function ResearchResultPage() {
  const { t } = useTranslation()
  const { evaluationId } = useParams<{ evaluationId: string }>()
  const [correctness, setCorrectness] = useState('')
  const [errorsOffset, setErrorsOffset] = useState(0)

  const detailQuery = useQuery({
    queryKey: ['research', 'evaluations', 'detail', evaluationId],
    queryFn: () => researchApi.evaluationDetail(evaluationId ?? ''),
    enabled: Boolean(evaluationId),
  })

  const isCompleted = detailQuery.data?.status === 'completed'

  const metricsQuery = useQuery({
    queryKey: ['research', 'evaluations', 'metrics', evaluationId],
    queryFn: () => researchApi.evaluationMetrics(evaluationId ?? ''),
    enabled: Boolean(evaluationId) && isCompleted,
  })

  const confusionMatrixQuery = useQuery({
    queryKey: ['research', 'evaluations', 'confusion-matrix', evaluationId],
    queryFn: () => researchApi.evaluationConfusionMatrix(evaluationId ?? ''),
    enabled: Boolean(evaluationId) && isCompleted,
  })

  const errorsQuery = useQuery({
    queryKey: ['research', 'evaluations', 'errors', evaluationId, correctness, errorsOffset],
    queryFn: () =>
      researchApi.listEvaluationErrors(evaluationId ?? '', {
        isCorrect: correctness === '' ? undefined : correctness === 'correct',
        limit: ERRORS_PAGE_SIZE,
        offset: errorsOffset,
      }),
    enabled: Boolean(evaluationId) && isCompleted,
  })

  if (!evaluationId) return null

  if (detailQuery.isLoading) {
    return <p className="text-base text-text-muted">{t('research.result.loading')}</p>
  }

  if (detailQuery.isError || !detailQuery.data) {
    const isNotFound =
      detailQuery.error instanceof ApiError && detailQuery.error.code === 'NOT_FOUND'
    return (
      <div className="flex max-w-xl flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-6">
        <h1 className="text-h1 text-text-primary">
          {isNotFound ? t('research.result.notFound') : t('research.result.error')}
        </h1>
        <Link to={routes.research} className="text-sm font-semibold text-primary">
          {t('research.result.backToOverview')}
        </Link>
      </div>
    )
  }

  const run = detailQuery.data
  const errorsTotal = errorsQuery.data?.total ?? 0
  const errorsFrom = errorsTotal === 0 ? 0 : errorsOffset + 1
  const errorsTo = Math.min(errorsOffset + ERRORS_PAGE_SIZE, errorsTotal)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 pb-24">
      <Link to={routes.research} className="text-sm font-semibold text-primary">
        ← {t('research.result.backToOverview')}
      </Link>

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <RunStatusBadge status={run.status} />
          <ResultClassificationBadge classification={run.result_classification} />
        </div>
        <h1 className="text-h1 text-text-primary">
          {run.model_id} <span className="text-text-muted">v{run.model_version}</span>
        </h1>
      </div>

      <p
        role="note"
        className="rounded-(--radius-md) bg-surface-subtle px-4 py-3 text-sm text-text-secondary"
      >
        {t('research.result.maturityNotice')}
      </p>

      <section className="rounded-(--radius-lg) border border-border bg-surface p-5">
        <h2 className="text-h3 text-text-primary">{t('research.result.details.title')}</h2>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm text-text-secondary">
          <dt className="font-medium text-text-primary">{t('research.result.details.dataset')}</dt>
          <dd>
            {run.dataset_id ? (
              <Link to={routes.datasetDetail(run.dataset_id)} className="text-primary">
                {run.dataset_id}
              </Link>
            ) : (
              '—'
            )}
          </dd>
          <dt className="font-medium text-text-primary">{t('research.result.details.split')}</dt>
          <dd>{run.split_name}</dd>
          <dt className="font-medium text-text-primary">
            {t('research.result.details.createdAt')}
          </dt>
          <dd>{formatDateTime(run.created_at)}</dd>
          {run.completed_at && (
            <>
              <dt className="font-medium text-text-primary">
                {t('research.result.details.completedAt')}
              </dt>
              <dd>{formatDateTime(run.completed_at)}</dd>
            </>
          )}
          {run.failure_reason && (
            <>
              <dt className="font-medium text-text-primary">
                {t('research.result.details.failureReason')}
              </dt>
              <dd>{run.failure_reason}</dd>
            </>
          )}
          {run.notes && (
            <>
              <dt className="font-medium text-text-primary">
                {t('research.result.details.notes')}
              </dt>
              <dd>{run.notes}</dd>
            </>
          )}
          <dt className="font-medium text-text-primary">{t('research.result.details.id')}</dt>
          <dd className="break-all font-mono text-xs">{run.id}</dd>
        </dl>
      </section>

      {isCompleted ? (
        <>
          {metricsQuery.data && (
            <MetricsPanel
              metrics={metricsQuery.data.scalar_metrics}
              counts={metricsQuery.data.counts}
            />
          )}

          {confusionMatrixQuery.data && (
            <ConfusionMatrixPanel confusionMatrix={confusionMatrixQuery.data} />
          )}

          <section className="flex flex-col gap-4">
            <div>
              <h2 className="text-h3 text-text-primary">{t('research.result.errors.title')}</h2>
              <p className="mt-1 text-sm text-text-secondary">
                {t('research.result.errors.subtitle')}
              </p>
            </div>

            <label className="flex max-w-xs flex-col gap-1 text-sm text-text-secondary">
              {t('research.result.errors.filterCorrectness')}
              <select
                value={correctness}
                onChange={(event) => {
                  setCorrectness(event.target.value)
                  setErrorsOffset(0)
                }}
                className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
              >
                <option value="">{t('research.result.errors.any')}</option>
                <option value="correct">{t('research.result.errors.correct')}</option>
                <option value="incorrect">{t('research.result.errors.incorrect')}</option>
              </select>
            </label>

            {errorsQuery.data && errorsQuery.data.items.length === 0 && (
              <p className="text-base text-text-muted">{t('research.result.errors.empty')}</p>
            )}

            {errorsQuery.data && errorsQuery.data.items.length > 0 && (
              <>
                <ul className="flex flex-col gap-2">
                  {errorsQuery.data.items.map((item) => (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-(--radius-md) border border-border bg-surface p-3 text-sm"
                    >
                      <div className="flex items-center gap-2">
                        {item.is_correct ? (
                          <CheckCircle2 aria-hidden size={18} className="shrink-0 text-success" />
                        ) : (
                          <XCircle aria-hidden size={18} className="shrink-0 text-danger" />
                        )}
                        <span className="font-mono text-xs text-text-muted">{item.sample_key}</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-text-secondary">
                        <span>
                          {t('research.result.errors.groundTruth')}: {item.ground_truth_label}
                        </span>
                        <span>
                          {t('research.result.errors.predicted')}: {item.predicted_class}
                        </span>
                        {item.confidence != null && (
                          <span>
                            {t('research.result.errors.confidence')}:{' '}
                            {formatPercent(item.confidence)}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm text-text-muted">
                    {t('research.result.errors.pageInfo', {
                      from: errorsFrom,
                      to: errorsTo,
                      total: errorsTotal,
                    })}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      disabled={errorsOffset === 0}
                      onClick={() => setErrorsOffset(Math.max(0, errorsOffset - ERRORS_PAGE_SIZE))}
                    >
                      {t('research.result.errors.previous')}
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={errorsOffset + ERRORS_PAGE_SIZE >= errorsTotal}
                      onClick={() => setErrorsOffset(errorsOffset + ERRORS_PAGE_SIZE)}
                    >
                      {t('research.result.errors.next')}
                    </Button>
                  </div>
                </div>
              </>
            )}
          </section>
        </>
      ) : (
        <p className="text-base text-text-muted">{t('research.result.noMetricsYet')}</p>
      )}
    </div>
  )
}
