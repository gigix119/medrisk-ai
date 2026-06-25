import { apiRequest } from '@/api/client'
import type { components } from '@/api/generated/schema'

export type EvaluationRunSummary = components['schemas']['EvaluationRunSummary']
export type EvaluationRunRead = components['schemas']['EvaluationRunRead']
export type EvaluationRunPage = components['schemas']['Page_EvaluationRunSummary_']
export type EvaluationMetricsRead = components['schemas']['EvaluationMetricsRead']
export type ConfusionMatrixRead = components['schemas']['ConfusionMatrixRead']
export type EvaluationSamplePredictionRead = components['schemas']['EvaluationSamplePredictionRead']
export type EvaluationErrorsPage = components['schemas']['Page_EvaluationSamplePredictionRead_']
export type MetricResult = components['schemas']['MetricResult']
export type ResultClassification = components['schemas']['ResultClassification']
export type RunStatus = components['schemas']['RunStatus']

export interface ListEvaluationsFilters {
  datasetId?: string
  studyId?: string
  status?: RunStatus
  limit?: number
  offset?: number
}

export interface ListEvaluationErrorsFilters {
  isCorrect?: boolean
  groundTruthLabel?: string
  predictedClass?: string
  minConfidence?: number
  maxConfidence?: number
  limit?: number
  offset?: number
}

/** Every value these endpoints return was already computed offline by `medrisk_research`'s
 * ingestion CLI (or, for the two audits, by pure-SQL checks - see app/research/services) and
 * merely persisted as JSON. There is no endpoint here that triggers training or evaluation;
 * `POST /research/evaluations` only creates a `pending` row, mirroring how training/evaluation
 * is CLI-only everywhere else in this codebase. */
export const researchApi = {
  listEvaluations(filters: ListEvaluationsFilters = {}): Promise<EvaluationRunPage> {
    return apiRequest<EvaluationRunPage>('/api/v1/research/evaluations', {
      query: {
        dataset_id: filters.datasetId,
        study_id: filters.studyId,
        status: filters.status,
        limit: filters.limit ?? 20,
        offset: filters.offset ?? 0,
      },
    })
  },

  evaluationDetail(evaluationId: string): Promise<EvaluationRunRead> {
    return apiRequest<EvaluationRunRead>(`/api/v1/research/evaluations/${evaluationId}`)
  },

  evaluationMetrics(evaluationId: string): Promise<EvaluationMetricsRead> {
    return apiRequest<EvaluationMetricsRead>(`/api/v1/research/evaluations/${evaluationId}/metrics`)
  },

  evaluationConfusionMatrix(evaluationId: string): Promise<ConfusionMatrixRead> {
    return apiRequest<ConfusionMatrixRead>(
      `/api/v1/research/evaluations/${evaluationId}/confusion-matrix`,
    )
  },

  listEvaluationErrors(
    evaluationId: string,
    filters: ListEvaluationErrorsFilters = {},
  ): Promise<EvaluationErrorsPage> {
    return apiRequest<EvaluationErrorsPage>(`/api/v1/research/evaluations/${evaluationId}/errors`, {
      query: {
        is_correct: filters.isCorrect,
        ground_truth_label: filters.groundTruthLabel,
        predicted_class: filters.predictedClass,
        min_confidence: filters.minConfidence,
        max_confidence: filters.maxConfidence,
        limit: filters.limit ?? 20,
        offset: filters.offset ?? 0,
      },
    })
  },
}
