import { useTranslation } from 'react-i18next'

import type { ConfusionMatrixRead } from '@/features/research/api'
import { formatPercent } from '@/lib/format'

/** Rows are the actual (ground-truth) class, columns the predicted class, in `class_labels`
 * order - matching `app.research.services.evaluation_service.build_confusion_matrix`, which
 * builds `matrix[i][j]` as count(actual=class_labels[i], predicted=class_labels[j]). */
export function ConfusionMatrixPanel({
  confusionMatrix,
}: {
  confusionMatrix: ConfusionMatrixRead
}) {
  const { t } = useTranslation()

  if (!confusionMatrix.available || !confusionMatrix.matrix || !confusionMatrix.class_labels) {
    return (
      <div className="rounded-(--radius-lg) border border-border bg-surface p-5">
        <h2 className="text-h3 text-text-primary">{t('research.result.confusionMatrix.title')}</h2>
        <p className="mt-3 text-sm text-text-muted">
          {confusionMatrix.reason ?? t('research.result.confusionMatrix.unavailable')}
        </p>
      </div>
    )
  }

  const { matrix, normalized_matrix: normalizedMatrix, class_labels: labels } = confusionMatrix

  return (
    <div className="rounded-(--radius-lg) border border-border bg-surface p-5">
      <h2 className="text-h3 text-text-primary">{t('research.result.confusionMatrix.title')}</h2>
      <p className="mt-1 text-sm text-text-muted">
        {t('research.result.confusionMatrix.axisHint')}
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="border-collapse text-sm">
          <thead>
            <tr>
              <th className="p-2 text-left font-medium text-text-muted">
                {t('research.result.confusionMatrix.actual')} \{' '}
                {t('research.result.confusionMatrix.predicted')}
              </th>
              {labels.map((label) => (
                <th
                  key={label}
                  className="border border-border p-2 text-center font-medium text-text-primary"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, rowIndex) => {
              const normalizedRow = normalizedMatrix?.[rowIndex]
              return (
                <tr key={labels[rowIndex]}>
                  <th className="border border-border p-2 text-left font-medium text-text-primary">
                    {labels[rowIndex]}
                  </th>
                  {row.map((value, columnIndex) => {
                    const normalizedValue = normalizedRow?.[columnIndex]
                    return (
                      <td
                        key={labels[columnIndex]}
                        className="border border-border p-3 text-center text-text-primary"
                      >
                        <div className="font-semibold">{value}</div>
                        {normalizedValue != null && (
                          <div className="text-xs text-text-muted">
                            {formatPercent(normalizedValue)}
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
