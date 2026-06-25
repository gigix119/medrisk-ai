import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { routes } from '@/config/routes'

export function NotFoundPage() {
  const { t } = useTranslation()

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-4 px-4 py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-text-muted">
        {t('notFound.kicker')}
      </p>
      <h1 className="text-h1 text-text-primary">{t('notFound.title')}</h1>
      <p className="text-lg text-text-secondary">{t('notFound.body')}</p>
      <Link
        to={routes.home}
        className="h-13 flex items-center justify-center rounded-(--radius-md) bg-primary px-6 text-base font-medium text-text-inverse"
      >
        {t('notFound.cta')}
      </Link>
    </div>
  )
}
