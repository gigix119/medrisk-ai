import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { queryKeys } from '@/app/query-client'
import { routes } from '@/config/routes'
import { datasetsApi } from '@/features/datasets/api'
import { useAuth } from '@/features/auth/use-auth'
import { modelApi } from '@/features/model/api'
import { predictionsApi } from '@/features/predictions/api'

export function DashboardPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const {
    data: model,
    isLoading: isModelLoading,
    isError: isModelError,
    error: modelError,
  } = useQuery({ queryKey: queryKeys.modelActive, queryFn: modelApi.active, retry: false })

  const datasetsQuery = useQuery({
    queryKey: ['datasets', 'list'],
    queryFn: () => datasetsApi.list(),
  })
  const totalRunsQuery = useQuery({
    queryKey: queryKeys.predictionsHistory({ limit: 1 }),
    queryFn: () => predictionsApi.history({ limit: 1 }),
  })
  const correctRunsQuery = useQuery({
    queryKey: queryKeys.predictionsHistory({ limit: 1, isCorrect: true }),
    queryFn: () => predictionsApi.history({ limit: 1, isCorrect: true }),
  })
  const incorrectRunsQuery = useQuery({
    queryKey: queryKeys.predictionsHistory({ limit: 1, isCorrect: false }),
    queryFn: () => predictionsApi.history({ limit: 1, isCorrect: false }),
  })

  const firstName = user?.full_name.split(' ')[0]

  return (
    <div className="flex max-w-3xl flex-col gap-8">
      <div>
        <h1 className="text-h1 text-text-primary">
          {firstName
            ? t('dashboard.welcomeBack', { name: firstName })
            : t('dashboard.welcomeBackGeneric')}
        </h1>
        <p className="mt-2 text-lg text-text-secondary">{t('dashboard.subtitle')}</p>
      </div>

      <div className="rounded-(--radius-lg) border border-border bg-surface p-6">
        <h2 className="text-h3 text-text-primary">{t('dashboard.datasetsCard.title')}</h2>
        <p className="mt-2 text-base text-text-secondary">{t('dashboard.datasetsCard.body')}</p>
        <Link
          to={routes.datasets}
          className="mt-4 inline-flex h-13 items-center justify-center rounded-(--radius-md) bg-primary px-6 text-base font-medium text-text-inverse"
        >
          {t('dashboard.datasetsCard.cta')}
        </Link>
      </div>

      <div className="rounded-(--radius-lg) border border-border bg-surface p-6">
        <h2 className="text-h3 text-text-primary">{t('dashboard.modelCard.title')}</h2>
        {isModelLoading && (
          <p className="mt-2 text-base text-text-muted">{t('dashboard.modelCard.loading')}</p>
        )}
        {isModelError && (
          <p className="mt-2 text-base text-warning">
            {modelError instanceof ApiError
              ? modelError.message
              : t('dashboard.modelCard.unavailable')}
          </p>
        )}
        {model && (
          <dl className="mt-2 grid grid-cols-2 gap-2 text-base text-text-secondary">
            <dt className="font-medium text-text-primary">{t('dashboard.modelCard.model')}</dt>
            <dd>
              {model.model_name} v{model.version}
            </dd>
            <dt className="font-medium text-text-primary">
              {t('dashboard.modelCard.architecture')}
            </dt>
            <dd>{model.architecture}</dd>
          </dl>
        )}
      </div>

      <div className="rounded-(--radius-lg) border border-border bg-surface p-6">
        <h2 className="text-h3 text-text-primary">{t('dashboard.statsCard.title')}</h2>
        <dl className="mt-2 grid grid-cols-2 gap-3 text-base text-text-secondary sm:grid-cols-4">
          <div>
            <dt className="text-sm font-medium text-text-primary">
              {t('dashboard.statsCard.datasetsAvailable')}
            </dt>
            <dd className="text-h3 text-text-primary">{datasetsQuery.data?.total ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-text-primary">
              {t('dashboard.statsCard.totalRuns')}
            </dt>
            <dd className="text-h3 text-text-primary">{totalRunsQuery.data?.total ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-text-primary">
              {t('dashboard.statsCard.correct')}
            </dt>
            <dd className="text-h3 text-positive">{correctRunsQuery.data?.total ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-text-primary">
              {t('dashboard.statsCard.incorrect')}
            </dt>
            <dd className="text-h3 text-warning">{incorrectRunsQuery.data?.total ?? '—'}</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
