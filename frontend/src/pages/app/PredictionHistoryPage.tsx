import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { queryKeys } from '@/app/query-client'
import { DecisionBadge } from '@/components/prediction-result/DecisionBadge'
import { routes } from '@/config/routes'
import { predictionsApi } from '@/features/predictions/api'
import { formatDateTime } from '@/lib/format'

const HISTORY_FILTERS = {}

export function PredictionHistoryPage() {
  const { t } = useTranslation()

  const historyQuery = useQuery({
    queryKey: queryKeys.predictionsHistory(HISTORY_FILTERS),
    queryFn: () => predictionsApi.history(HISTORY_FILTERS),
  })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 pb-24">
      <div>
        <h1 className="text-h1 text-text-primary">{t('analysis.history.title')}</h1>
        <p className="mt-2 text-base text-text-secondary">{t('analysis.history.intro')}</p>
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
            to={routes.analyze}
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
                <DecisionBadge decision={item.decision} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
