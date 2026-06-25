import { useTranslation } from 'react-i18next'

interface InfoSection {
  heading: string
  body: string
}

export type InfoPageKey =
  | 'howItWorks'
  | 'technology'
  | 'model'
  | 'privacy'
  | 'limitations'
  | 'accessibility'
  | 'status'

export interface InfoPageProps {
  pageKey: InfoPageKey
}

/** Small, consistent template for the public info pages (how it works, technology, model,
 * privacy, limitations, accessibility, status) - content lives in i18n, not in components,
 * so each page is just a key and stays translated. */
export function InfoPage({ pageKey }: InfoPageProps) {
  const { t } = useTranslation()
  const base = `infoPages.${pageKey}`
  const sections = t(`${base}.sections`, { returnObjects: true }) as InfoSection[]

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-16 lg:py-24">
      <div className="flex flex-col gap-3">
        <p className="text-sm font-medium uppercase tracking-wide text-text-muted">
          {t(`${base}.kicker`)}
        </p>
        <h1 className="text-h1 text-text-primary">{t(`${base}.title`)}</h1>
        <p className="text-lg text-text-secondary">{t(`${base}.intro`)}</p>
      </div>

      <div className="flex flex-col gap-4">
        {sections.map((section) => (
          <div
            key={section.heading}
            className="rounded-(--radius-lg) border border-border bg-surface p-6"
          >
            <h2 className="text-h3 text-text-primary">{section.heading}</h2>
            <p className="mt-2 text-base text-text-secondary">{section.body}</p>
          </div>
        ))}
      </div>

      <p className="reading-measure text-sm text-text-muted">{t('common.disclaimer')}</p>
    </div>
  )
}
