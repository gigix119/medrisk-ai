import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { brand } from '@/config/brand'
import { routes } from '@/config/routes'

export function LandingPage() {
  const { t } = useTranslation()

  return (
    <div className="mx-auto max-w-6xl px-4 py-16 lg:py-24">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 text-center">
        <p className="text-sm font-medium uppercase tracking-wide text-text-muted">
          Research portfolio project · Educational use only
        </p>
        <h1 className="text-display text-text-primary">
          Understand an AI prediction — not just the final number.
        </h1>
        <p className="reading-measure mx-auto text-lg text-text-secondary">{brand.tagline}</p>
        <div className="mx-auto flex flex-col gap-3 sm:flex-row">
          <Link
            to={routes.demo}
            className="h-13 flex items-center justify-center rounded-(--radius-md) bg-primary px-6 text-base font-medium text-text-inverse"
          >
            {t('nav.tryDemo')}
          </Link>
          <Link
            to={routes.howItWorks}
            className="h-13 flex items-center justify-center rounded-(--radius-md) border border-border px-6 text-base font-medium text-text-primary"
          >
            See how it works
          </Link>
        </div>
        <p className="text-sm text-text-muted">{brand.disclaimer}</p>
      </div>
    </div>
  )
}
