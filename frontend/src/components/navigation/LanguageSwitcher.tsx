import { useTranslation } from 'react-i18next'

const LOCALES = [
  { code: 'en', label: 'EN' },
  { code: 'pl', label: 'PL' },
] as const

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation()

  return (
    <div className="flex items-center gap-1" role="group" aria-label={t('nav.language')}>
      {LOCALES.map((locale) => (
        <button
          key={locale.code}
          type="button"
          onClick={() => void i18n.changeLanguage(locale.code)}
          aria-pressed={i18n.language === locale.code}
          className={
            i18n.language === locale.code
              ? 'rounded-(--radius-sm) bg-primary-soft px-2 py-1 text-sm font-semibold text-primary'
              : 'rounded-(--radius-sm) px-2 py-1 text-sm font-semibold text-text-muted hover:text-text-primary'
          }
        >
          {locale.label}
        </button>
      ))}
    </div>
  )
}
