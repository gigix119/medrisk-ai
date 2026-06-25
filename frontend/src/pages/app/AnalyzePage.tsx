import { useTranslation } from 'react-i18next'

import { DatasetGrid } from '@/components/datasets/DatasetGrid'

/** Repurposed in place (Phase 6): this used to be an arbitrary-image-upload flow. It is now
 * a thin entry point into the dataset registry - no upload control (drag-and-drop, file
 * picker, camera input) is reachable from here or anywhere else in the product UI. The old
 * upload components (components/upload/*) and the upload endpoint itself still exist for
 * internal/test use, but are not wired into any reachable page. */
export function AnalyzePage() {
  const { t } = useTranslation()

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 pb-24">
      <div>
        <h1 className="text-h1 text-text-primary">{t('analysis.title')}</h1>
        <p className="mt-2 text-base text-text-secondary">{t('analysis.intro')}</p>
      </div>

      <p
        role="note"
        className="rounded-(--radius-md) bg-surface-subtle px-4 py-3 text-sm text-text-secondary"
      >
        {t('analysis.disclaimer')}
      </p>

      <DatasetGrid />
    </div>
  )
}
