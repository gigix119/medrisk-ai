import { Navigate } from 'react-router-dom'

import { routes } from '@/config/routes'
import { useAuth } from '@/features/auth/use-auth'

/** Handles a direct visit to /demo (typed URL, external link, browser back/forward) with
 * the same rule as <DemoLink>: authenticated users land on the Dataset Explorer, everyone
 * else is sent to log in first, with a path back to it. */
export function DemoRedirectPage() {
  const { isAuthenticated, isInitializing } = useAuth()

  if (isInitializing) return null

  if (isAuthenticated) {
    return <Navigate to={routes.datasets} replace />
  }

  return <Navigate to={routes.login} state={{ from: { pathname: routes.datasets } }} replace />
}
