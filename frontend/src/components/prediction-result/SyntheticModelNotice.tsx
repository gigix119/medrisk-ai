import { Microscope } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function SyntheticModelNotice({ syntheticOnly }: { syntheticOnly: boolean | null }) {
  const { t } = useTranslation()
  if (syntheticOnly === false) return null

  return (
    <div
      role="note"
      className="flex items-start gap-3 rounded-(--radius-md) bg-warning-soft px-4 py-3 text-sm text-warning"
    >
      <Microscope aria-hidden size={20} className="mt-0.5 shrink-0" />
      <p>
        {syntheticOnly === null
          ? t('analysis.syntheticNotice.unknown')
          : t('analysis.syntheticNotice.synthetic')}
      </p>
    </div>
  )
}
