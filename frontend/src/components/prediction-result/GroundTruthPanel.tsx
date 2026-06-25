import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type {
  ClassProbability,
  GroundTruthViewModel,
} from '@/features/predictions/result-view-model'
import { cn } from '@/lib/cn'
import { formatPercent } from '@/lib/format'

export interface GroundTruthPanelProps {
  groundTruth: GroundTruthViewModel
  /** Used for the error-analysis "probability gap" between the ground-truth class and the
   * predicted class - null when probabilities aren't available for this result. */
  classProbabilities: ClassProbability[] | null
}

export function GroundTruthPanel({ groundTruth, classProbabilities }: GroundTruthPanelProps) {
  const { t } = useTranslation()
  const { isCorrect, label, predictedLabel } = groundTruth

  const groundTruthProbability = classProbabilities?.find(
    (item) => item.label === label,
  )?.probability
  const predictedProbability = classProbabilities?.find(
    (item) => item.label === predictedLabel,
  )?.probability
  const probabilityGap =
    groundTruthProbability != null && predictedProbability != null
      ? Math.abs(groundTruthProbability - predictedProbability)
      : null

  return (
    <div className="flex flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-5">
      <h2 className="text-h3 text-text-primary">{t('analysis.result.groundTruth.title')}</h2>

      <div
        className={cn(
          'flex items-start gap-3 rounded-(--radius-md) px-4 py-3 text-sm',
          isCorrect ? 'bg-positive-soft text-positive' : 'bg-warning-soft text-warning',
        )}
      >
        {isCorrect ? (
          <CheckCircle2 aria-hidden size={20} className="mt-0.5 shrink-0" />
        ) : (
          <AlertTriangle aria-hidden size={20} className="mt-0.5 shrink-0" />
        )}
        <p>
          <span className="font-semibold">
            {t(
              isCorrect
                ? 'analysis.result.groundTruth.match.correct'
                : 'analysis.result.groundTruth.match.incorrect',
            )}
          </span>
          {' — '}
          {t(
            isCorrect
              ? 'analysis.result.groundTruth.match.correctExplanation'
              : 'analysis.result.groundTruth.match.incorrectExplanation',
          )}
        </p>
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm text-text-secondary">
        <dt className="font-medium text-text-primary">
          {t('analysis.result.groundTruth.groundTruthLabel')}
        </dt>
        <dd>{label}</dd>
        <dt className="font-medium text-text-primary">
          {t('analysis.result.groundTruth.predictedLabel')}
        </dt>
        <dd>{predictedLabel ?? '—'}</dd>
      </dl>

      {!isCorrect && (
        <div className="flex flex-col gap-2 rounded-(--radius-md) bg-surface-subtle p-4">
          <h3 className="text-sm font-semibold text-text-primary">
            {t('analysis.result.groundTruth.errorAnalysis.title')}
          </h3>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm text-text-secondary">
            <dt className="font-medium text-text-primary">
              {t('analysis.result.groundTruth.errorAnalysis.predicted')}
            </dt>
            <dd>{predictedLabel ?? '—'}</dd>
            <dt className="font-medium text-text-primary">
              {t('analysis.result.groundTruth.errorAnalysis.actual')}
            </dt>
            <dd>{label}</dd>
            {probabilityGap != null && (
              <>
                <dt className="font-medium text-text-primary">
                  {t('analysis.result.groundTruth.errorAnalysis.probabilityGap')}
                </dt>
                <dd>{formatPercent(probabilityGap)}</dd>
              </>
            )}
          </dl>
          <p className="text-xs text-text-muted">
            {t('analysis.result.groundTruth.errorAnalysis.note')}
          </p>
        </div>
      )}

      <details className="rounded-(--radius-md) border border-border">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-text-primary">
          {t('analysis.result.groundTruth.reproducibility.title')}
        </summary>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 px-4 pb-4 text-sm text-text-secondary">
          <dt className="font-medium text-text-primary">
            {t('analysis.result.groundTruth.reproducibility.dataset')}
          </dt>
          <dd>{groundTruth.datasetName ?? '—'}</dd>
          <dt className="font-medium text-text-primary">
            {t('analysis.result.groundTruth.reproducibility.datasetVersion')}
          </dt>
          <dd>{groundTruth.datasetVersion ?? '—'}</dd>
          <dt className="font-medium text-text-primary">
            {t('analysis.result.groundTruth.reproducibility.sampleKey')}
          </dt>
          <dd className="break-all font-mono text-xs">{groundTruth.sampleKey ?? '—'}</dd>
          <dt className="font-medium text-text-primary">
            {t('analysis.result.groundTruth.reproducibility.split')}
          </dt>
          <dd>{groundTruth.split ?? '—'}</dd>
        </dl>
      </details>
    </div>
  )
}
