import { Link } from 'react-router-dom'

import { routes } from '@/config/routes'

export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-4 px-4 py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-text-muted">404</p>
      <h1 className="text-h1 text-text-primary">Page not found</h1>
      <p className="text-lg text-text-secondary">
        The page you're looking for doesn't exist or may have moved.
      </p>
      <Link
        to={routes.home}
        className="h-13 flex items-center justify-center rounded-(--radius-md) bg-primary px-6 text-base font-medium text-text-inverse"
      >
        Go to homepage
      </Link>
    </div>
  )
}
