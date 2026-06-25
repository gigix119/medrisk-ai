import { useMutation } from '@tanstack/react-query'

import { predictionsApi } from '@/features/predictions/api'

/** Never retried automatically (see predictionsApi.predictHistopathology) - a duplicate
 * submission would run real inference twice against the synchronous endpoint. */
export function useAnalyzeImage() {
  return useMutation({
    mutationFn: predictionsApi.predictHistopathology,
  })
}
