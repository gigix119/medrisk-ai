import type { ActiveModelResponse } from '@/features/model/api'

import type { HistopathologyPredictionResponse, PredictionRead } from './api'

export interface ClassProbability {
  label: string
  probability: number
  isPredicted: boolean
}

export type GradCamViewModel =
  | { kind: 'available'; dataUrl: string; width: number | null; height: number | null }
  | { kind: 'unavailable'; reason: 'not_requested' | 'failed' | 'disabled' | 'never_persisted' }

export type OriginalImageViewModel =
  | { kind: 'available'; previewUrl: string; fileName: string | null }
  | { kind: 'not-stored' }

export interface PredictionResultViewModel {
  predictionId: string
  status: string
  decision: string | null
  predictedClass: string | null
  confidenceScore: number | null
  calibratedProbability: number | null
  modelName: string | null
  modelVersion: string | null
  /** null means "unknown" (e.g. a historical prediction whose model version no longer
   * matches the currently active model) - render as unknown, never assume false. */
  syntheticOnly: boolean | null
  createdAt: string
  classProbabilities: ClassProbability[] | null
  gradCam: GradCamViewModel
  image: OriginalImageViewModel
}

function buildClassProbabilities(
  calibratedProbability: number | null | undefined,
  predictedClass: string | null | undefined,
  positiveClass: string | null | undefined,
  classNames: readonly [string, string] | null | undefined,
): ClassProbability[] | null {
  if (calibratedProbability == null || !positiveClass || !classNames) return null
  const negativeClass = classNames.find((name) => name !== positiveClass)
  if (!negativeClass) return null

  return classNames.map((name) => ({
    label: name,
    probability: name === positiveClass ? calibratedProbability : 1 - calibratedProbability,
    isPredicted: name === predictedClass,
  }))
}

function mapExplanation(
  explanation: HistopathologyPredictionResponse['explanation'],
): GradCamViewModel {
  if (explanation.status === 'available' && explanation.data) {
    return {
      kind: 'available',
      dataUrl: `data:${explanation.mime_type ?? 'image/png'};base64,${explanation.data}`,
      width: explanation.width ?? null,
      height: explanation.height ?? null,
    }
  }
  if (explanation.status === 'failed') return { kind: 'unavailable', reason: 'failed' }
  if (explanation.status === 'disabled') return { kind: 'unavailable', reason: 'disabled' }
  return { kind: 'unavailable', reason: 'not_requested' }
}

export function fromRichResult(
  result: HistopathologyPredictionResponse,
  classNames: readonly [string, string] | null,
  image: OriginalImageViewModel,
): PredictionResultViewModel {
  return {
    predictionId: result.prediction_id,
    status: result.status,
    decision: result.decision,
    predictedClass: result.predicted_class,
    confidenceScore: result.confidence_score,
    calibratedProbability: result.calibrated_probability,
    modelName: result.model.model_name,
    modelVersion: result.model.version,
    syntheticOnly: result.model.synthetic_only,
    createdAt: result.created_at,
    classProbabilities: buildClassProbabilities(
      result.calibrated_probability,
      result.predicted_class,
      result.positive_class,
      classNames,
    ),
    gradCam: mapExplanation(result.explanation),
    image,
  }
}

export function fromHistoryRead(
  prediction: PredictionRead,
  activeModel: ActiveModelResponse | undefined,
): PredictionResultViewModel {
  const versionMatches = activeModel != null && activeModel.version === prediction.model_version

  return {
    predictionId: prediction.id,
    status: prediction.status,
    decision: prediction.decision,
    predictedClass: prediction.predicted_class,
    confidenceScore: prediction.confidence_score,
    calibratedProbability: prediction.calibrated_probability,
    modelName: prediction.model_name,
    modelVersion: prediction.model_version,
    syntheticOnly: versionMatches ? activeModel.synthetic_only : null,
    createdAt: prediction.created_at,
    classProbabilities: versionMatches
      ? buildClassProbabilities(
          prediction.calibrated_probability,
          prediction.predicted_class,
          activeModel.positive_class,
          activeModel.class_names,
        )
      : null,
    gradCam: { kind: 'unavailable', reason: 'never_persisted' },
    image: { kind: 'not-stored' },
  }
}
