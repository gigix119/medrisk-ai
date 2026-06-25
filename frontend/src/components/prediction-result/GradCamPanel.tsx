import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type {
  GradCamViewModel,
  OriginalImageViewModel,
} from '@/features/predictions/result-view-model'

export interface GradCamPanelProps {
  gradCam: GradCamViewModel
  originalImage: OriginalImageViewModel
}

export function GradCamPanel({ gradCam, originalImage }: GradCamPanelProps) {
  const { t } = useTranslation()
  const [opacity, setOpacity] = useState(0.6)
  const hasOriginal = originalImage.kind === 'available'

  return (
    <div className="flex flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-5">
      <div>
        <h3 className="text-h3 text-text-primary">{t('analysis.result.gradcam.title')}</h3>
        <p className="mt-1 text-sm text-text-secondary">
          {t('analysis.result.gradcam.explanation')}
        </p>
      </div>

      {gradCam.kind === 'unavailable' ? (
        <p className="rounded-(--radius-md) bg-surface-subtle px-4 py-3 text-sm text-text-muted">
          {t(`analysis.result.gradcam.unavailable.${gradCam.reason}`)}
        </p>
      ) : (
        <>
          <div className="relative mx-auto aspect-square w-full max-w-xs overflow-hidden rounded-(--radius-md) border border-border bg-surface-subtle">
            {hasOriginal && (
              <img
                src={originalImage.previewUrl}
                alt={t('analysis.result.gradcam.originalAlt')}
                className="absolute inset-0 h-full w-full object-cover"
              />
            )}
            <img
              src={gradCam.dataUrl}
              alt={t('analysis.result.gradcam.overlayAlt')}
              className="absolute inset-0 h-full w-full object-cover"
              style={{ opacity: hasOriginal ? opacity : 1 }}
            />
          </div>

          {hasOriginal && (
            <div className="flex flex-col gap-2">
              <label htmlFor="gradcam-opacity" className="text-sm font-medium text-text-primary">
                {t('analysis.result.gradcam.opacityLabel')}
              </label>
              <input
                id="gradcam-opacity"
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={opacity}
                onChange={(event) => setOpacity(Number(event.target.value))}
                className="h-2 w-full accent-primary"
                aria-valuetext={`${Math.round(opacity * 100)}%`}
              />
            </div>
          )}

          <p className="text-xs text-text-muted">{t('analysis.result.gradcam.disclaimer')}</p>
        </>
      )}
    </div>
  )
}
