import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { ApiError } from '@/api/errors'
import { Button } from '@/components/ui/Button'
import { DatasetCard } from '@/components/datasets/DatasetCard'
import { datasetsApi } from '@/features/datasets/api'

/** Shared by the Dataset Explorer page and the repurposed /app/analyze entry point - both
 * just need "show me the available datasets," with no upload control anywhere. */
export function DatasetGrid() {
  const { t } = useTranslation()
  const datasetsQuery = useQuery({
    queryKey: ['datasets', 'list'],
    queryFn: () => datasetsApi.list(),
  })

  if (datasetsQuery.isLoading) {
    return <p className="text-base text-text-muted">{t('datasets.explorer.loading')}</p>
  }

  if (datasetsQuery.isError) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-base text-danger">
          {datasetsQuery.error instanceof ApiError
            ? datasetsQuery.error.message
            : t('datasets.explorer.error')}
        </p>
        <Button variant="secondary" onClick={() => void datasetsQuery.refetch()}>
          {t('analysis.tryAgain')}
        </Button>
      </div>
    )
  }

  if (!datasetsQuery.data || datasetsQuery.data.items.length === 0) {
    return <p className="text-base text-text-muted">{t('datasets.explorer.empty')}</p>
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {datasetsQuery.data.items.map((dataset) => (
        <DatasetCard key={dataset.id} dataset={dataset} />
      ))}
    </div>
  )
}
