import type { ComponentProps } from 'react'
import { Link } from 'react-router-dom'

import { routes } from '@/config/routes'
import { useAuth } from '@/features/auth/use-auth'

type DemoLinkProps = Omit<ComponentProps<typeof Link>, 'to' | 'state'>

/** "Explore datasets" everywhere in the public site: authenticated users go straight to the
 * Dataset Explorer, everyone else goes to login with a path back to it afterward. */
export function DemoLink(props: DemoLinkProps) {
  const { isAuthenticated } = useAuth()

  if (isAuthenticated) {
    return <Link to={routes.datasets} {...props} />
  }

  return <Link to={routes.login} state={{ from: { pathname: routes.datasets } }} {...props} />
}
