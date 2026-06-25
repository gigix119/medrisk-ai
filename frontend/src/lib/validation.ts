import { z } from 'zod'

/** Mirrors app/schemas/auth.py MIN/MAX_PASSWORD_LENGTH - keep these two in sync. */
export const MIN_PASSWORD_LENGTH = 12
export const MAX_PASSWORD_LENGTH = 128

type TranslateFn = (key: string, options?: Record<string, unknown>) => string

/** Built per-render with the active `t` so validation messages follow the selected
 * language, not just the static UI text around the form. */
export function buildEmailSchema(t: TranslateFn) {
  return z.string().trim().toLowerCase().email(t('validation.email'))
}

export function buildPasswordSchema(t: TranslateFn) {
  return z
    .string()
    .min(MIN_PASSWORD_LENGTH, t('validation.passwordMin', { count: MIN_PASSWORD_LENGTH }))
    .max(MAX_PASSWORD_LENGTH, t('validation.passwordMax', { count: MAX_PASSWORD_LENGTH }))
}
