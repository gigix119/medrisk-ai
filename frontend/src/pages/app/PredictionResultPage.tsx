import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import { queryKeys } from '@/app/query-client'
import { DecisionBadge } from '@/components/prediction-result/DecisionBadge'
import { GradCamPanel } from '@/components/prediction-result/GradCamPanel'
import { ProbabilityBars } from '@/components/prediction-result/ProbabilityBars'
import { SyntheticModelNotice } from '@/components/prediction-result/SyntheticModelNotice'
import { Button } from '@/components/ui/Button'
import { routes } from '@/config/routes'
import { modelApi } from '@/features/model/api'
import { predictionsApi, type HistopathologyPredictionResponse } from '@/features/predictions/api'
import {
  fromHistoryRead,
  fromRichResult,
  type PredictionResultViewModel,
} from '@/features/predictions/result-view-model'
import { formatDateTime, formatPercent } from '@/lib/format'

interface FreshResultState {
  result: HistopathologyPredictionResponse
  previewUrl: string
  originalFileName: string
}

function readFreshState(state: unknown, predictionId: string): FreshResultState | null {
  if (typeof state !== 'object' || state === null || !('result' in state)) return null
  const candidate = state as FreshResultState
  return candidate.result?.prediction_id === predictionId ? candidate : null
}

export function PredictionResultPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { predictionId } = useParams<{ predictionId: string }>()
  const location = useLocation()
  const revokedRef = useRef(false)

  const freshState = predictionId ? readFreshState(location.state, predictionId) : null

  useEffect(() => {
    return () => {
      if (freshState && !revokedRef.current) {
        revokedRef.current = true
        URL.revokeObjectURL(freshState.previewUrl)
      }
    }
    // Revoke exactly once, when this page unmounts - not on every re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const modelQuery = useQuery({ queryKey: queryKeys.modelActive, queryFn: modelApi.active })

  const detailQuery = useQuery({
    queryKey: queryKeys.predictionDetail(predictionId ?? ''),
    queryFn: () => predictionsApi.detail(predictionId ?? ''),
    enabled: !freshState && Boolean(predictionId),
  })

  if (!predictionId) return null

  if (freshState) {
    const viewModel = fromRichResult(freshState.result, modelQuery.data?.class_names ?? null, {
      kind: 'available',
      previewUrl: freshState.previewUrl,
      fileName: freshState.originalFileName,
    })
    return <ResultView viewModel={viewModel} />
  }

  if (detailQuery.isLoading || modelQuery.isLoading) {
    return <p className="text-base text-text-muted">{t('analysis.result.loading')}</p>
  }

  if (detailQuery.isError) {
    const isNotFound =
      detailQuery.error instanceof ApiError && detailQuery.error.code === 'NOT_FOUND'
    return (
      <div className="flex max-w-xl flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-6">
        <h1 className="text-h1 text-text-primary">
          {isNotFound ? t('analysis.result.notFoundTitle') : t('analysis.result.errorTitle')}
        </h1>
        <p className="text-base text-text-secondary">
          {detailQuery.error instanceof ApiError
            ? detailQuery.error.message
            : t('analysis.result.genericError')}
        </p>
        <div className="flex gap-3">
          {!isNotFound && (
            <Button variant="secondary" onClick={() => void detailQuery.refetch()}>
              {t('analysis.tryAgain')}
            </Button>
          )}
          <Button onClick={() => navigate(routes.predictions)}>
            {t('analysis.result.backToHistory')}
          </Button>
        </div>
      </div>
    )
  }

  if (!detailQuery.data) return null

  const viewModel = fromHistoryRead(detailQuery.data, modelQuery.data)
  return <ResultView viewModel={viewModel} />
}

function ResultView({ viewModel }: { viewModel: PredictionResultViewModel }) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 pb-24">
      <div className="flex flex-col gap-3">
        <DecisionBadge decision={viewModel.decision} />
        <h1 className="text-h1 text-text-primary">
          {viewModel.predictedClass
            ? t('analysis.result.predictedClassHeading', { className: viewModel.predictedClass })
            : t('analysis.result.unknownHeading')}
        </h1>
        <p className="text-base text-text-secondary">
          {t('analysis.result.interpretationGuidance')}
        </p>
      </div>

      <p
        role="note"
        className="rounded-(--radius-md) bg-surface-subtle px-4 py-3 text-sm text-text-secondary"
      >
        {t('analysis.disclaimer')}
      </p>

      <SyntheticModelNotice syntheticOnly={viewModel.syntheticOnly} />

      <div className="rounded-(--radius-lg) border border-border bg-surface p-5">
        <h2 className="text-h3 text-text-primary">{t('analysis.result.probabilities.title')}</h2>
        {viewModel.classProbabilities ? (
          <>
            <p className="mt-1 text-sm text-text-secondary">
              {t('analysis.result.probabilities.subtitle')}
            </p>
            <div className="mt-4">
              <ProbabilityBars probabilities={viewModel.classProbabilities} />
            </div>
          </>
        ) : viewModel.calibratedProbability != null ? (
          <p className="mt-3 text-base text-text-primary">
            {t('analysis.result.probabilities.singleClass', {
              className: viewModel.predictedClass ?? t('analysis.result.unknownClass'),
              probability: formatPercent(
                viewModel.confidenceScore ?? viewModel.calibratedProbability,
              ),
            })}
          </p>
        ) : (
          <p className="mt-3 text-sm text-text-muted">
            {t('analysis.result.probabilities.unavailable')}
          </p>
        )}
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="flex flex-col gap-3 rounded-(--radius-lg) border border-border bg-surface p-5">
          <h2 className="text-h3 text-text-primary">{t('analysis.result.image.title')}</h2>
          {viewModel.image.kind === 'available' ? (
            <img
              src={viewModel.image.previewUrl}
              alt={t('analysis.result.image.alt')}
              className="aspect-square w-full rounded-(--radius-md) border border-border object-cover"
            />
          ) : (
            <p className="text-sm text-text-muted">{t('analysis.result.image.notStored')}</p>
          )}
        </div>

        <GradCamPanel gradCam={viewModel.gradCam} originalImage={viewModel.image} />
      </div>

      <div className="rounded-(--radius-lg) border border-border bg-surface p-5">
        <h2 className="text-h3 text-text-primary">{t('analysis.result.details.title')}</h2>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm text-text-secondary">
          <dt className="font-medium text-text-primary">{t('analysis.result.details.model')}</dt>
          <dd>
            {viewModel.modelName ?? '—'}
            {viewModel.modelVersion ? ` v${viewModel.modelVersion}` : ''}
          </dd>
          <dt className="font-medium text-text-primary">
            {t('analysis.result.details.timestamp')}
          </dt>
          <dd>{formatDateTime(viewModel.createdAt)}</dd>
          <dt className="font-medium text-text-primary">{t('analysis.result.details.id')}</dt>
          <dd className="break-all font-mono text-xs">{viewModel.predictionId}</dd>
        </dl>
      </div>

      <p className="text-sm text-text-muted">{t('analysis.result.limitationNotice')}</p>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Button size="full" onClick={() => navigate(routes.analyze)}>
          {t('analysis.result.analyzeAnother')}
        </Button>
        <Button size="full" variant="secondary" onClick={() => navigate(routes.predictions)}>
          {t('analysis.result.backToHistory')}
        </Button>
      </div>
    </div>
  )
}
