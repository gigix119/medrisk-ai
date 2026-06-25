import type { PredictOnSampleResponse } from '@/features/datasets/api'
import type { ActiveModelResponse } from '@/features/model/api'

import type { HistopathologyPredictionResponse, PredictionRead } from './api'

export interface ClassProbability {
  label: string
  probability: number
  isPredicted: boolean
}

export interface GroundTruthViewModel {
  label: string
  predictedLabel: string | null
  isCorrect: boolean
  datasetId: string
  /** Null when this view model was built from a flat, historical PredictionRead (the
   * dataset's display name/version/sample-key are not denormalized onto that record) -
   * the reproducibility panel renders those rows as unavailable rather than guessing. */
  datasetName: string | null
  datasetVersion: string | null
  sampleKey: string | null
  split: string | null
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
  /** Non-null only for predictions that ran against a known dataset sample (Phase 6) - null
   * for both the legacy upload flow and for historical reads where this wasn't recorded. */
  groundTruth: GroundTruthViewModel | null
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
    groundTruth: null,
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
    groundTruth:
      prediction.dataset_id && prediction.ground_truth_label
        ? {
            label: prediction.ground_truth_label,
            predictedLabel: prediction.predicted_class,
            isCorrect: Boolean(prediction.is_correct),
            datasetId: prediction.dataset_id,
            datasetName: null,
            datasetVersion: null,
            sampleKey: null,
            split: prediction.split,
          }
        : null,
  }
}

export function fromSampleResult(
  result: PredictOnSampleResponse,
  classNames: readonly [string, string] | null,
  image: OriginalImageViewModel,
): PredictionResultViewModel {
  return {
    predictionId: result.prediction_id,
    status: 'completed',
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
    groundTruth: {
      label: result.ground_truth_label,
      predictedLabel: result.predicted_class,
      isCorrect: result.is_correct,
      datasetId: result.dataset_id,
      datasetName: result.dataset_name,
      datasetVersion: result.dataset_version,
      sampleKey: result.sample_key,
      split: result.split,
    },
  }
}
