import { format } from 'date-fns'

export function formatPercent(probability: number): string {
  return `${(probability * 100).toFixed(1)}%`
}

export function formatDateTime(isoTimestamp: string): string {
  return format(new Date(isoTimestamp), 'd MMM yyyy, HH:mm')
}
