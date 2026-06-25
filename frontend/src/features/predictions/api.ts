import { apiRequest } from '@/api/client'
import type { components } from '@/api/generated/schema'

export type HistopathologyPredictionResponse =
  components['schemas']['HistopathologyPredictionResponse']
export type PredictionRead = components['schemas']['PredictionRead']
export type PredictionPage = components['schemas']['Page_PredictionRead_']

export interface PredictHistopathologyInput {
  file: File
  includeExplanation?: boolean
  clientReference?: string
}

export interface HistoryFilters {
  limit?: number
  offset?: number
  module?: PredictionRead['module']
  status?: PredictionRead['status']
  decision?: string
  modelVersion?: string
  datasetId?: string
  split?: string
  predictedClass?: string
  isCorrect?: boolean
}

export const predictionsApi = {
  /** Never retried automatically - a duplicate submission would run real inference twice. */
  predictHistopathology({
    file,
    includeExplanation = false,
    clientReference,
  }: PredictHistopathologyInput): Promise<HistopathologyPredictionResponse> {
    const form = new FormData()
    form.set('file', file)
    form.set('include_explanation', String(includeExplanation))
    if (clientReference) form.set('client_reference', clientReference)

    return apiRequest<HistopathologyPredictionResponse>('/api/v1/predictions/histopathology', {
      method: 'POST',
      rawBody: form,
      retryOnUnauthorized: false,
    })
  },

  history(filters: HistoryFilters = {}): Promise<PredictionPage> {
    return apiRequest<PredictionPage>('/api/v1/predictions/history', {
      query: {
        limit: filters.limit ?? 20,
        offset: filters.offset ?? 0,
        module: filters.module,
        status: filters.status,
        decision: filters.decision,
        model_version: filters.modelVersion,
        dataset_id: filters.datasetId,
        split: filters.split,
        predicted_class: filters.predictedClass,
        is_correct: filters.isCorrect,
      },
    })
  },

  detail(predictionId: string): Promise<PredictionRead> {
    return apiRequest<PredictionRead>(`/api/v1/predictions/${predictionId}`)
  },
}
