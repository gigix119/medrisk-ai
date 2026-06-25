import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { queryKeys } from '@/app/query-client'
import { Button } from '@/components/ui/Button'
import { routes } from '@/config/routes'
import { datasetsApi } from '@/features/datasets/api'
import { useSampleImageUrl } from '@/features/datasets/sample-image'
import { usePredictOnSample } from '@/features/datasets/use-predict-on-sample'
import { modelApi } from '@/features/model/api'

export function DatasetSampleDetailPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { datasetId, sampleId } = useParams<{ datasetId: string; sampleId: string }>()

  const datasetQuery = useQuery({
    queryKey: ['datasets', 'detail', datasetId],
    queryFn: () => datasetsApi.detail(datasetId ?? ''),
    enabled: Boolean(datasetId),
  })
  const sampleQuery = useQuery({
    queryKey: ['datasets', 'sample-detail', datasetId, sampleId],
    queryFn: () => datasetsApi.sampleDetail(datasetId ?? '', sampleId ?? ''),
    enabled: Boolean(datasetId) && Boolean(sampleId),
  })
  const modelQuery = useQuery({ queryKey: queryKeys.modelActive, queryFn: modelApi.active })
  const predictMutation = usePredictOnSample()

  const { url: imageUrl } = useSampleImageUrl(sampleQuery.data?.image_url)

  if (!datasetId || !sampleId) return null

  if (sampleQuery.isLoading || datasetQuery.isLoading) {
    return <p className="text-base text-text-muted">{t('datasets.sampleDetail.loading')}</p>
  }

  if (sampleQuery.isError || datasetQuery.isError || !sampleQuery.data || !datasetQuery.data) {
    const isNotFound =
      (sampleQuery.error instanceof ApiError && sampleQuery.error.code === 'NOT_FOUND') ||
      (datasetQuery.error instanceof ApiError && datasetQuery.error.code === 'NOT_FOUND')
    return (
      <div className="flex max-w-xl flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-6">
        <h1 className="text-h1 text-text-primary">
          {isNotFound ? t('datasets.sampleDetail.notFound') : t('datasets.sampleDetail.error')}
        </h1>
        <Link to={routes.datasetDetail(datasetId)} className="text-sm font-semibold text-primary">
          {t('datasets.sampleDetail.backToDataset')}
        </Link>
      </div>
    )
  }

  const sample = sampleQuery.data
  const dataset = datasetQuery.data
  const model = modelQuery.data

  // Re-bind as new consts: TypeScript's narrowing from the `if (!datasetId...) return null`
  // guard above does not carry into the nested closure below.
  const safeDatasetId = datasetId
  const safeSampleId = sampleId

  function handleRunInference() {
    if (predictMutation.isPending) return
    predictMutation.mutate(
      { datasetId: safeDatasetId, sampleId: safeSampleId, includeExplanation: true },
      {
        onSuccess: (result) => {
          navigate(routes.predictionDetail(result.prediction_id), {
            state: { sampleResult: result, datasetId: safeDatasetId, sampleId: safeSampleId },
          })
        },
      },
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 pb-24">
      <Link to={routes.datasetDetail(datasetId)} className="text-sm font-semibold text-primary">
        ← {t('datasets.sampleDetail.backToDataset')}
      </Link>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="aspect-square w-full overflow-hidden rounded-(--radius-lg) border border-border bg-surface-subtle">
          {imageUrl && (
            <img src={imageUrl} alt={sample.sample_key} className="h-full w-full object-cover" />
          )}
        </div>

        <div className="flex flex-col gap-3">
          <h1 className="text-h1 text-text-primary">{dataset.name}</h1>
          <div className="flex flex-wrap gap-2">
            {sample.is_synthetic && (
              <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-semibold text-warning">
                {t('datasets.sampleDetail.syntheticBadge')}
              </span>
            )}
            {dataset.is_public && (
              <span className="rounded-full bg-surface-subtle px-3 py-1 text-xs font-semibold text-text-secondary">
                {t('datasets.sampleDetail.publicBadge')}
              </span>
            )}
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm text-text-secondary">
            <dt className="font-medium text-text-primary">
              {t('datasets.sampleDetail.groundTruth')}
            </dt>
            <dd>{sample.ground_truth_label}</dd>
            <dt className="font-medium text-text-primary">{t('datasets.sampleDetail.split')}</dt>
            <dd>{sample.split}</dd>
            <dt className="font-medium text-text-primary">
              {t('datasets.sampleDetail.dimensions')}
            </dt>
            <dd>
              {sample.width}×{sample.height}
            </dd>
            <dt className="font-medium text-text-primary">{t('datasets.sampleDetail.checksum')}</dt>
            <dd className="break-all font-mono text-xs">{sample.checksum_sha256.slice(0, 16)}…</dd>
          </dl>
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-(--radius-lg) border border-border bg-surface p-5">
        <h2 className="text-h3 text-text-primary">{t('datasets.sampleDetail.beforeRun.title')}</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm text-text-secondary">
          <dt className="font-medium text-text-primary">
            {t('datasets.sampleDetail.beforeRun.model')}
          </dt>
          <dd>{model ? `${model.model_name} v${model.version}` : '—'}</dd>
          <dt className="font-medium text-text-primary">
            {t('datasets.sampleDetail.beforeRun.inputSize')}
          </dt>
          <dd>
            {model
              ? `${model.input_contract.input_width}×${model.input_contract.input_height}`
              : '—'}
          </dd>
          {dataset.preprocessing_summary && (
            <>
              <dt className="font-medium text-text-primary">
                {t('datasets.sampleDetail.beforeRun.preprocessing')}
              </dt>
              <dd>{dataset.preprocessing_summary}</dd>
            </>
          )}
        </dl>
        <p className="text-sm text-text-secondary">{t('datasets.sampleDetail.beforeRun.notice')}</p>
      </div>

      <p
        role="note"
        className="rounded-(--radius-md) bg-surface-subtle px-4 py-3 text-sm text-text-secondary"
      >
        {t('analysis.disclaimer')}
      </p>

      {predictMutation.isError && (
        <p role="alert" className="text-sm font-medium text-danger">
          {predictMutation.error instanceof Error
            ? predictMutation.error.message
            : t('datasets.sampleDetail.runError')}
        </p>
      )}

      <Button size="full" onClick={handleRunInference} disabled={predictMutation.isPending}>
        {predictMutation.isPending
          ? t('datasets.sampleDetail.running')
          : t('datasets.sampleDetail.runCta')}
      </Button>
    </div>
  )
}
