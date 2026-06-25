import { apiRequest } from '@/api/client'
import type { components } from '@/api/generated/schema'

export type DatasetRead = components['schemas']['DatasetRead']
export type DatasetPage = components['schemas']['Page_DatasetRead_']
export type DatasetSampleRead = components['schemas']['DatasetSampleRead']
export type DatasetSamplePage = components['schemas']['Page_DatasetSampleRead_']
export type PredictOnSampleResponse = components['schemas']['PredictOnSampleResponse']

export interface ListSamplesFilters {
  split?: string
  classIndex?: number
  limit?: number
  offset?: number
}

export interface PredictOnSampleInput {
  datasetId: string
  sampleId: string
  includeExplanation?: boolean
  clientReference?: string
}

export const datasetsApi = {
  list(limit = 20, offset = 0): Promise<DatasetPage> {
    return apiRequest<DatasetPage>('/api/v1/datasets', { query: { limit, offset } })
  },

  detail(datasetId: string): Promise<DatasetRead> {
    return apiRequest<DatasetRead>(`/api/v1/datasets/${datasetId}`)
  },

  listSamples(datasetId: string, filters: ListSamplesFilters = {}): Promise<DatasetSamplePage> {
    return apiRequest<DatasetSamplePage>(`/api/v1/datasets/${datasetId}/samples`, {
      query: {
        split: filters.split,
        class_index: filters.classIndex,
        limit: filters.limit ?? 20,
        offset: filters.offset ?? 0,
      },
    })
  },

  sampleDetail(datasetId: string, sampleId: string): Promise<DatasetSampleRead> {
    return apiRequest<DatasetSampleRead>(`/api/v1/datasets/${datasetId}/samples/${sampleId}`)
  },

  /** Never retried automatically (matches predictionsApi.predictHistopathology) - a
   * duplicate submission would run real inference twice against the synchronous endpoint. */
  predictOnSample({
    datasetId,
    sampleId,
    includeExplanation = false,
    clientReference,
  }: PredictOnSampleInput): Promise<PredictOnSampleResponse> {
    return apiRequest<PredictOnSampleResponse>(
      `/api/v1/datasets/${datasetId}/samples/${sampleId}/predict`,
      {
        method: 'POST',
        body: {
          include_explanation: includeExplanation,
          client_reference: clientReference,
        },
        retryOnUnauthorized: false,
      },
    )
  },
}
