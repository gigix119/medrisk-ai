import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { DemoLink } from '@/components/navigation/DemoLink'
import { brand } from '@/config/brand'
import { routes } from '@/config/routes'

export function LandingPage() {
  const { t, i18n } = useTranslation()
  const tagline = i18n.language === 'pl' ? brand.taglinePl : brand.tagline

  return (
    <div className="mx-auto max-w-6xl px-4 py-16 lg:py-24">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 text-center">
        <p className="text-sm font-medium uppercase tracking-wide text-text-muted">
          {t('landing.kicker')}
        </p>
        <h1 className="text-display text-text-primary">{t('landing.heroTitle')}</h1>
        <p className="reading-measure mx-auto text-lg text-text-secondary">{tagline}</p>
        <div className="mx-auto flex flex-col gap-3 sm:flex-row">
          <DemoLink className="h-13 flex items-center justify-center rounded-(--radius-md) bg-primary px-6 text-base font-medium text-text-inverse">
            {t('nav.tryDemo')}
          </DemoLink>
          <Link
            to={routes.howItWorks}
            className="h-13 flex items-center justify-center rounded-(--radius-md) border border-border px-6 text-base font-medium text-text-primary"
          >
            {t('landing.howItWorksCta')}
          </Link>
        </div>
        <p className="text-sm text-text-muted">{t('common.disclaimer')}</p>
        <p className="text-sm font-medium text-text-secondary">{t('landing.noUploadNotice')}</p>
      </div>
    </div>
  )
}
