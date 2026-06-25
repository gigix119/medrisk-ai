import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo } from 'react'

import { apiRequestBlob } from '@/api/client'

/** The sample image endpoint requires auth, so a plain `<img src="...">` can't carry the
 * bearer token - fetch it as a blob and expose an object URL instead. `createObjectURL` is
 * synchronous, so the URL itself is a plain memo (matching AnalyzePage's local-file-preview
 * pattern) - only the *cleanup* (revoking it) needs an effect. */
export function useSampleImageUrl(imageUrl: string | undefined) {
  const blobQuery = useQuery({
    queryKey: ['dataset-sample-image', imageUrl],
    queryFn: () => apiRequestBlob(imageUrl as string),
    enabled: Boolean(imageUrl),
    staleTime: Infinity,
  })

  const objectUrl = useMemo(
    () => (blobQuery.data ? URL.createObjectURL(blobQuery.data) : null),
    [blobQuery.data],
  )

  useEffect(() => {
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [objectUrl])

  return { url: objectUrl, isLoading: blobQuery.isLoading, error: blobQuery.error }
}
