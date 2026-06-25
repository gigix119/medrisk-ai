import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { DatasetSampleCard } from '@/components/datasets/DatasetSampleCard'
import { Button } from '@/components/ui/Button'
import { routes } from '@/config/routes'
import { datasetsApi } from '@/features/datasets/api'

const PAGE_SIZE = 12

export function DatasetDetailPage() {
  const { t } = useTranslation()
  const { datasetId } = useParams<{ datasetId: string }>()
  const [split, setSplit] = useState<string>('')
  const [classIndex, setClassIndex] = useState<string>('')
  const [offset, setOffset] = useState(0)

  const datasetQuery = useQuery({
    queryKey: ['datasets', 'detail', datasetId],
    queryFn: () => datasetsApi.detail(datasetId ?? ''),
    enabled: Boolean(datasetId),
  })

  const samplesQuery = useQuery({
    queryKey: ['datasets', 'samples', datasetId, split, classIndex, offset],
    queryFn: () =>
      datasetsApi.listSamples(datasetId ?? '', {
        split: split || undefined,
        classIndex: classIndex === '' ? undefined : Number(classIndex),
        limit: PAGE_SIZE,
        offset,
      }),
    enabled: Boolean(datasetId),
  })

  if (!datasetId) return null

  if (datasetQuery.isLoading) {
    return <p className="text-base text-text-muted">{t('datasets.detail.loading')}</p>
  }

  if (datasetQuery.isError || !datasetQuery.data) {
    const isNotFound =
      datasetQuery.error instanceof ApiError && datasetQuery.error.code === 'NOT_FOUND'
    return (
      <div className="flex max-w-xl flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-6">
        <h1 className="text-h1 text-text-primary">
          {isNotFound ? t('datasets.detail.notFound') : t('datasets.detail.error')}
        </h1>
        <Link to={routes.datasets} className="text-sm font-semibold text-primary">
          {t('datasets.detail.backToExplorer')}
        </Link>
      </div>
    )
  }

  const dataset = datasetQuery.data
  const total = samplesQuery.data?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + PAGE_SIZE, total)

  function resetAndSet(setter: () => void) {
    setter()
    setOffset(0)
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 pb-24">
      <div className="flex flex-col gap-3">
        <Link to={routes.datasets} className="text-sm font-semibold text-primary">
          ← {t('datasets.detail.backToExplorer')}
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-h1 text-text-primary">{dataset.name}</h1>
          <span className="rounded-full bg-surface-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
            v{dataset.version}
          </span>
          {dataset.is_synthetic && (
            <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-semibold text-warning">
              {t('datasets.explorer.syntheticBadge')}
            </span>
          )}
        </div>
        <p className="text-base text-text-secondary">{dataset.description}</p>
      </div>

      <section className="rounded-(--radius-lg) border border-border bg-surface p-5">
        <h2 className="text-h3 text-text-primary">{t('datasets.detail.overview.title')}</h2>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm text-text-secondary sm:grid-cols-3">
          <dt className="font-medium text-text-primary">{t('datasets.detail.overview.samples')}</dt>
          <dd className="col-span-2 sm:col-span-1">{dataset.sample_count}</dd>
          <dt className="font-medium text-text-primary">{t('datasets.detail.overview.classes')}</dt>
          <dd className="col-span-2 sm:col-span-1">{dataset.classes.join(', ')}</dd>
          <dt className="font-medium text-text-primary">
            {t('datasets.detail.overview.dimensions')}
          </dt>
          <dd className="col-span-2 sm:col-span-1">
            {dataset.image_width}×{dataset.image_height}
          </dd>
          <dt className="font-medium text-text-primary">
            {t('datasets.detail.overview.channels')}
          </dt>
          <dd className="col-span-2 sm:col-span-1">{dataset.image_channels}</dd>
          <dt className="font-medium text-text-primary">{t('datasets.detail.overview.splits')}</dt>
          <dd className="col-span-2 sm:col-span-1">{dataset.split_names.join(', ')}</dd>
          {dataset.preprocessing_summary && (
            <>
              <dt className="font-medium text-text-primary">
                {t('datasets.detail.overview.preprocessing')}
              </dt>
              <dd className="col-span-2 sm:col-span-1">{dataset.preprocessing_summary}</dd>
            </>
          )}
        </dl>
      </section>

      <section className="rounded-(--radius-lg) border border-border bg-surface p-5">
        <h2 className="text-h3 text-text-primary">{t('datasets.detail.intendedUse.title')}</h2>
        <dl className="mt-3 flex flex-col gap-3 text-sm text-text-secondary">
          <div>
            <dt className="font-medium text-text-primary">
              {t('datasets.detail.intendedUse.allowed')}
            </dt>
            <dd>{dataset.intended_use}</dd>
          </div>
          <div>
            <dt className="font-medium text-text-primary">
              {t('datasets.detail.intendedUse.prohibited')}
            </dt>
            <dd>{dataset.prohibited_use}</dd>
          </div>
          <div>
            <dt className="font-medium text-text-primary">
              {t('datasets.detail.intendedUse.limitations')}
            </dt>
            <dd>{dataset.known_limitations}</dd>
          </div>
          <div>
            <dt className="font-medium text-text-primary">
              {t('datasets.detail.intendedUse.ethics')}
            </dt>
            <dd>{dataset.ethical_notes}</dd>
          </div>
        </dl>
      </section>

      <section className="rounded-(--radius-lg) border border-border bg-surface p-5">
        <h2 className="text-h3 text-text-primary">{t('datasets.detail.source.title')}</h2>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm text-text-secondary">
          <dt className="font-medium text-text-primary">{t('datasets.detail.source.source')}</dt>
          <dd>{dataset.source_name}</dd>
          <dt className="font-medium text-text-primary">{t('datasets.detail.source.license')}</dt>
          <dd>{dataset.license_name}</dd>
          {dataset.citation && (
            <>
              <dt className="font-medium text-text-primary">
                {t('datasets.detail.source.citation')}
              </dt>
              <dd>{dataset.citation}</dd>
            </>
          )}
        </dl>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-h3 text-text-primary">{t('datasets.detail.browser.title')}</h2>

        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1 text-sm text-text-secondary">
            {t('datasets.detail.browser.filterSplit')}
            <select
              value={split}
              onChange={(event) => resetAndSet(() => setSplit(event.target.value))}
              className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
            >
              <option value="">{t('datasets.detail.browser.allSplits')}</option>
              {dataset.split_names.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm text-text-secondary">
            {t('datasets.detail.browser.filterClass')}
            <select
              value={classIndex}
              onChange={(event) => resetAndSet(() => setClassIndex(event.target.value))}
              className="h-11 rounded-(--radius-md) border border-border bg-surface px-3 text-base text-text-primary"
            >
              <option value="">{t('datasets.detail.browser.allClasses')}</option>
              {dataset.classes.map((name, index) => (
                <option key={name} value={index}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {samplesQuery.isLoading && (
          <p className="text-base text-text-muted">{t('datasets.explorer.loading')}</p>
        )}

        {samplesQuery.data && samplesQuery.data.items.length === 0 && (
          <p className="text-base text-text-muted">{t('datasets.detail.browser.empty')}</p>
        )}

        {samplesQuery.data && samplesQuery.data.items.length > 0 && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {samplesQuery.data.items.map((sample) => (
                <DatasetSampleCard key={sample.id} datasetId={datasetId} sample={sample} />
              ))}
            </div>

            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-text-muted">
                {t('datasets.detail.browser.pageInfo', { from, to, total })}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  {t('datasets.detail.browser.previous')}
                </Button>
                <Button
                  variant="secondary"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  {t('datasets.detail.browser.next')}
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
