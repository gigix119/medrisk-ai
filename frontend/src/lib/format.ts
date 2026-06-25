import { format } from 'date-fns'

export function formatPercent(probability: number): string {
  return `${(probability * 100).toFixed(1)}%`
}

export function formatDateTime(isoTimestamp: string): string {
  return format(new Date(isoTimestamp), 'd MMM yyyy, HH:mm')
}

/** Deliberately generic (no per-metric percent/ratio assumptions) - this renders whatever
 * numeric value a metric carries (a 0-1 ratio, a loss, a count-derived statistic, ...)
 * without guessing its natural unit. */
export function formatMetricValue(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(4)
}
