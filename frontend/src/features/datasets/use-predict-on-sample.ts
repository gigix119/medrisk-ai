import { useMutation } from '@tanstack/react-query'

import { datasetsApi } from '@/features/datasets/api'

/** Never retried automatically (see datasetsApi.predictOnSample) - a duplicate submission
 * would run real inference twice against the synchronous endpoint. */
export function usePredictOnSample() {
  return useMutation({
    mutationFn: datasetsApi.predictOnSample,
  })
}
