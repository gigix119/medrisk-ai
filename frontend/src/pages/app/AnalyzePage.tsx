import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { queryKeys } from '@/app/query-client'
import { ApiError } from '@/api/errors'
import { AnalysisProgress } from '@/components/upload/AnalysisProgress'
import { ImageDropzone } from '@/components/upload/ImageDropzone'
import { SelectedFilePreview } from '@/components/upload/SelectedFilePreview'
import { SyntheticModelNotice } from '@/components/prediction-result/SyntheticModelNotice'
import { Button } from '@/components/ui/Button'
import { routes } from '@/config/routes'
import { MAX_UPLOAD_BYTES } from '@/features/analysis/constants'
import { useAnalyzeImage } from '@/features/analysis/use-analyze'
import {
  formatFileSize,
  validateImageFile,
  type ImageValidationError,
  type ImageValidationResult,
} from '@/features/analysis/image-file'
import { modelApi } from '@/features/model/api'

type Validation = 'idle' | 'validating' | ImageValidationResult
type TranslateFn = (key: string, options?: Record<string, unknown>) => string

function getValidationErrorMessage(error: ImageValidationError, t: TranslateFn): string {
  switch (error.code) {
    case 'EMPTY':
      return t('analysis.upload.errors.empty')
    case 'UNSUPPORTED_TYPE':
      return t('analysis.upload.errors.unsupportedType')
    case 'TOO_LARGE':
      return t('analysis.upload.errors.tooLarge', { maxSize: formatFileSize(MAX_UPLOAD_BYTES) })
    case 'CORRUPT':
      return t('analysis.upload.errors.corrupt')
    case 'DIMENSIONS_MISMATCH':
      return t('analysis.upload.errors.dimensionsMismatch', {
        expectedWidth: error.expected.width,
        expectedHeight: error.expected.height,
        actualWidth: error.actual.width,
        actualHeight: error.actual.height,
      })
  }
}

export function AnalyzePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const modelQuery = useQuery({ queryKey: queryKeys.modelActive, queryFn: modelApi.active })
  const analyzeMutation = useAnalyzeImage()

  const [file, setFile] = useState<File | null>(null)
  const [validation, setValidation] = useState<Validation>('idle')
  const ownershipTransferredRef = useRef(false)

  // Derived from `file`, not effect-driven state - createObjectURL is synchronous, so this
  // can be a plain memo. Only the *cleanup* (revoking it) needs an effect.
  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])

  useEffect(() => {
    return () => {
      if (previewUrl && !ownershipTransferredRef.current) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  useEffect(() => {
    if (!file || !modelQuery.data) return
    let cancelled = false
    const requiredDimensions = {
      width: modelQuery.data.input_contract.input_width,
      height: modelQuery.data.input_contract.input_height,
    }
    void validateImageFile(file, requiredDimensions).then((result) => {
      if (!cancelled) setValidation(result)
    })
    return () => {
      cancelled = true
    }
  }, [file, modelQuery.data])

  function handleFileSelected(selected: File) {
    ownershipTransferredRef.current = false
    analyzeMutation.reset()
    setFile(selected)
    setValidation('validating')
  }

  function handleRemove() {
    ownershipTransferredRef.current = false
    analyzeMutation.reset()
    setFile(null)
    setValidation('idle')
  }

  function handleAnalyze() {
    if (!file || analyzeMutation.isPending) return
    analyzeMutation.mutate(
      { file, includeExplanation: true },
      {
        onSuccess: (result) => {
          ownershipTransferredRef.current = true
          navigate(routes.predictionDetail(result.prediction_id), {
            state: { result, previewUrl, originalFileName: file.name },
          })
        },
      },
    )
  }

  if (modelQuery.isLoading) {
    return <p className="text-base text-text-muted">{t('analysis.upload.loadingModel')}</p>
  }

  if (modelQuery.isError || !modelQuery.data) {
    return (
      <div className="flex max-w-xl flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-6">
        <h1 className="text-h1 text-text-primary">{t('analysis.title')}</h1>
        <p className="text-base text-danger">
          {modelQuery.error instanceof ApiError
            ? modelQuery.error.message
            : t('analysis.upload.modelUnavailable')}
        </p>
        <Button variant="secondary" onClick={() => void modelQuery.refetch()}>
          {t('analysis.tryAgain')}
        </Button>
      </div>
    )
  }

  const model = modelQuery.data
  const isSubmitting = analyzeMutation.isPending
  const validationResult = validation !== 'idle' && validation !== 'validating' ? validation : null
  const validationError = validationResult && !validationResult.ok ? validationResult.error : null
  const validDimensions =
    validationResult && validationResult.ok
      ? { width: validationResult.width, height: validationResult.height }
      : null

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 pb-24">
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

      <p className="text-sm text-text-muted">
        {t('analysis.upload.requirements', {
          width: model.input_contract.input_width,
          height: model.input_contract.input_height,
          maxSize: formatFileSize(MAX_UPLOAD_BYTES),
        })}
      </p>

      {!file && <ImageDropzone onFileSelected={handleFileSelected} />}

      {file && previewUrl && (
        <SelectedFilePreview
          previewUrl={previewUrl}
          fileName={file.name}
          mimeType={file.type || t('analysis.upload.unknownType')}
          sizeBytes={file.size}
          dimensions={validDimensions}
          onRemove={handleRemove}
        />
      )}

      {validation === 'validating' && (
        <p className="text-sm text-text-muted">{t('analysis.upload.validating')}</p>
      )}

      {validationError && (
        <p role="alert" className="text-sm font-medium text-danger">
          {getValidationErrorMessage(validationError, t)}
        </p>
      )}

      {validDimensions && !isSubmitting && (
        <div className="flex flex-col gap-4 rounded-(--radius-lg) border border-border bg-surface p-5">
          <h2 className="text-h3 text-text-primary">{t('analysis.confirm.title')}</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm text-text-secondary">
            <dt className="font-medium text-text-primary">{t('analysis.confirm.model')}</dt>
            <dd>
              {model.model_name} v{model.version}
            </dd>
          </dl>
          <SyntheticModelNotice syntheticOnly={model.synthetic_only} />
          <p className="text-sm text-text-secondary">{t('analysis.confirm.processingNotice')}</p>
        </div>
      )}

      {isSubmitting && <AnalysisProgress />}

      {!isSubmitting && analyzeMutation.isError && (
        <p role="alert" className="text-sm font-medium text-danger">
          {analyzeMutation.error instanceof Error
            ? analyzeMutation.error.message
            : t('analysis.submitError')}
        </p>
      )}

      {validDimensions && (
        <Button size="full" onClick={handleAnalyze} disabled={isSubmitting}>
          {isSubmitting ? t('analysis.analyzing') : t('analysis.analyzeCta')}
        </Button>
      )}
    </div>
  )
}
