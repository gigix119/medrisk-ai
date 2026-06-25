import { UploadCloud } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/cn'

export interface ImageDropzoneProps {
  onFileSelected: (file: File) => void
  disabled?: boolean
  describedById?: string
}

export function ImageDropzone({ onFileSelected, disabled, describedById }: ImageDropzoneProps) {
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  function openPicker() {
    if (!disabled) inputRef.current?.click()
  }

  function handleFiles(files: FileList | null) {
    const file = files?.[0]
    if (file) onFileSelected(file)
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-describedby={describedById}
      onClick={openPicker}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          openPicker()
        }
      }}
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setIsDragging(false)
        if (!disabled) handleFiles(event.dataTransfer.files)
      }}
      className={cn(
        'flex min-h-56 flex-col items-center justify-center gap-3 rounded-(--radius-lg) border-2 border-dashed border-border-strong bg-surface px-6 py-10 text-center transition-colors',
        isDragging && 'border-primary bg-primary-soft',
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:border-primary',
      )}
    >
      <UploadCloud aria-hidden size={40} className="text-text-muted" />
      <p className="text-base font-medium text-text-primary">{t('analysis.upload.dropTitle')}</p>
      <p className="text-sm text-text-muted">{t('analysis.upload.dropHint')}</p>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg"
        className="sr-only"
        disabled={disabled}
        aria-label={t('analysis.upload.inputLabel')}
        onChange={(event) => {
          handleFiles(event.target.files)
          // Reset so selecting the same file again after a "remove" still fires onChange.
          event.target.value = ''
        }}
      />
    </div>
  )
}
