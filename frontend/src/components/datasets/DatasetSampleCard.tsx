import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { routes } from '@/config/routes'
import type { DatasetSampleRead } from '@/features/datasets/api'
import { useSampleImageUrl } from '@/features/datasets/sample-image'

export function DatasetSampleCard({
  datasetId,
  sample,
}: {
  datasetId: string
  sample: DatasetSampleRead
}) {
  const { t } = useTranslation()
  const { url } = useSampleImageUrl(sample.image_url)

  return (
    <Link
      to={routes.datasetSampleDetail(datasetId, sample.id)}
      className="flex flex-col gap-2 rounded-(--radius-lg) border border-border bg-surface p-3 hover:border-primary"
    >
      <div className="aspect-square w-full overflow-hidden rounded-(--radius-md) bg-surface-subtle">
        {url && <img src={url} alt={sample.sample_key} className="h-full w-full object-cover" />}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-1 text-xs text-text-secondary">
        <span className="font-medium text-text-primary">{sample.ground_truth_label}</span>
        <span className="rounded-full bg-surface-subtle px-2 py-0.5">{sample.split}</span>
      </div>
      <span className="text-xs font-semibold text-primary">
        {t('datasets.detail.browser.inspectCta')}
      </span>
    </Link>
  )
}
