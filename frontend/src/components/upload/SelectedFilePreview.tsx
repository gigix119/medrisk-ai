import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { formatFileSize } from '@/features/analysis/image-file'

export interface SelectedFilePreviewProps {
  previewUrl: string
  fileName: string
  mimeType: string
  sizeBytes: number
  dimensions: { width: number; height: number } | null
  onRemove: () => void
}

export function SelectedFilePreview({
  previewUrl,
  fileName,
  mimeType,
  sizeBytes,
  dimensions,
  onRemove,
}: SelectedFilePreviewProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-4 sm:flex-row sm:items-center">
      <img
        src={previewUrl}
        alt={t('analysis.upload.previewAlt')}
        className="h-32 w-32 shrink-0 self-center rounded-(--radius-md) border border-border object-cover"
      />
      <div className="flex flex-1 flex-col gap-1 overflow-hidden">
        <p className="truncate text-base font-medium text-text-primary" title={fileName}>
          {fileName}
        </p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-sm text-text-muted">
          <dt>{t('analysis.upload.fileType')}</dt>
          <dd>{mimeType}</dd>
          <dt>{t('analysis.upload.fileSize')}</dt>
          <dd>{formatFileSize(sizeBytes)}</dd>
          <dt>{t('analysis.upload.fileDimensions')}</dt>
          <dd>{dimensions ? `${dimensions.width} × ${dimensions.height} px` : '—'}</dd>
        </dl>
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="flex h-11 items-center justify-center gap-2 self-start rounded-(--radius-md) px-3 text-sm font-medium text-text-secondary hover:bg-surface-subtle sm:self-center"
      >
        <X aria-hidden size={18} />
        {t('analysis.upload.remove')}
      </button>
    </div>
  )
}
