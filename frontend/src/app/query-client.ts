import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/api/errors'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry auth/permission failures - retrying won't change the outcome.
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          return false
        }
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
})

export const queryKeys = {
  authMe: ['auth', 'me'] as const,
  modelActive: ['model', 'active'] as const,
  modelHealth: ['model', 'health'] as const,
  predictionsHistory: (filters: object) => ['predictions', 'history', filters] as const,
  predictionDetail: (id: string) => ['predictions', 'detail', id] as const,
}
