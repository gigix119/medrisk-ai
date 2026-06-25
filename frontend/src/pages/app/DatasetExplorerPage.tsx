import { useTranslation } from 'react-i18next'

import { DatasetGrid } from '@/components/datasets/DatasetGrid'

export function DatasetExplorerPage() {
  const { t } = useTranslation()

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 pb-24">
      <div>
        <h1 className="text-h1 text-text-primary">{t('datasets.explorer.title')}</h1>
        <p className="mt-2 text-base text-text-secondary">{t('datasets.explorer.intro')}</p>
      </div>

      <DatasetGrid />
    </div>
  )
}
