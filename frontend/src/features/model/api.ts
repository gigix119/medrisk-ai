import { apiRequest } from '@/api/client'
import type { components } from '@/api/generated/schema'

export type ActiveModelResponse = components['schemas']['ActiveModelResponse']
export type ModelHealthResponse = components['schemas']['ModelHealthResponse']

export const modelApi = {
  active(): Promise<ActiveModelResponse> {
    return apiRequest<ActiveModelResponse>('/api/v1/models/active')
  },

  health(): Promise<ModelHealthResponse> {
    return apiRequest<ModelHealthResponse>('/health/model', { skipAuth: true })
  },
}
