import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { queryKeys } from '@/app/query-client'
import { routes } from '@/config/routes'
import { useAuth } from '@/features/auth/use-auth'
import { modelApi } from '@/features/model/api'

export function DashboardPage() {
  const { user } = useAuth()
  const {
    data: model,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: queryKeys.modelActive,
    queryFn: modelApi.active,
    retry: false,
  })

  const firstName = user?.full_name.split(' ')[0]

  return (
    <div className="flex max-w-3xl flex-col gap-8">
      <div>
        <h1 className="text-h1 text-text-primary">
          {firstName ? `Welcome back, ${firstName}` : 'Welcome back'}
        </h1>
        <p className="mt-2 text-lg text-text-secondary">
          Ready to explore a new research analysis?
        </p>
      </div>

      <div className="rounded-(--radius-lg) border border-border bg-surface p-6">
        <h2 className="text-h3 text-text-primary">Start a new analysis</h2>
        <p className="mt-2 text-base text-text-secondary">
          Upload a compatible histopathology patch and run it through the research model. Raw images
          are processed in memory and are not stored.
        </p>
        <Link
          to={routes.analyze}
          className="mt-4 inline-flex h-13 items-center justify-center rounded-(--radius-md) bg-primary px-6 text-base font-medium text-text-inverse"
        >
          Start a new analysis
        </Link>
      </div>

      <div className="rounded-(--radius-lg) border border-border bg-surface p-6">
        <h2 className="text-h3 text-text-primary">System readiness</h2>
        {isLoading && <p className="mt-2 text-base text-text-muted">Checking model status…</p>}
        {isError && (
          <p className="mt-2 text-base text-warning">
            {error instanceof ApiError
              ? error.message
              : 'No histopathology model is currently active.'}
          </p>
        )}
        {model && (
          <dl className="mt-2 grid grid-cols-2 gap-2 text-base text-text-secondary">
            <dt className="font-medium text-text-primary">Model</dt>
            <dd>
              {model.model_name} v{model.version}
            </dd>
            <dt className="font-medium text-text-primary">Architecture</dt>
            <dd>{model.architecture}</dd>
          </dl>
        )}
      </div>
    </div>
  )
}
