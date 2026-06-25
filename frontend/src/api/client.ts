import { env } from '@/config/environment'

import { ApiError, type ApiErrorDetail, NetworkError } from './errors'
import { tokenManager } from './token-manager'

const DEFAULT_TIMEOUT_MS = 30_000

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Pre-built body (FormData, URLSearchParams) sent as-is, skipping JSON.stringify. */
  rawBody?: BodyInit
  query?: Record<string, string | number | boolean | undefined>
  signal?: AbortSignal
  timeoutMs?: number
  /** Auth endpoints (login/register/refresh) must not attempt the 401-refresh-and-retry
   * dance on themselves. */
  skipAuth?: boolean
  /** The prediction POST must never be silently retried - a duplicate submission would
   * run inference twice. */
  retryOnUnauthorized?: boolean
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(path.replace(/^\//, ''), `${env.apiBaseUrl}/`)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

export async function refreshTokens(
  refreshToken: string,
): Promise<{ accessToken: string; refreshToken: string }> {
  const response = await fetch(buildUrl('/api/v1/auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!response.ok) throw new Error('Refresh failed')
  const data = (await response.json()) as { access_token: string; refresh_token: string }
  return { accessToken: data.access_token, refreshToken: data.refresh_token }
}

async function parseErrorBody(response: Response): Promise<ApiErrorDetail> {
  try {
    const data = (await response.json()) as { error?: ApiErrorDetail }
    if (data.error) return data.error
  } catch {
    // Non-JSON error body (e.g. a proxy's HTML error page) - fall through to generic.
  }
  return { code: 'UNKNOWN', message: `Request failed with status ${response.status}.` }
}

async function performFetch(path: string, options: RequestOptions): Promise<Response> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  options.signal?.addEventListener('abort', () => controller.abort())

  const headers = new Headers()
  let body: BodyInit | undefined

  if (options.rawBody !== undefined) {
    body = options.rawBody
  } else if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(options.body)
  }

  if (!options.skipAuth) {
    const accessToken = tokenManager.getAccessToken()
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  }

  try {
    return await fetch(buildUrl(path, options.query), {
      method: options.method ?? 'GET',
      headers,
      body,
      signal: controller.signal,
      credentials: 'omit',
    })
  } catch (cause) {
    throw new NetworkError(cause)
  } finally {
    clearTimeout(timeout)
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await performFetch(path, options)

  const shouldRetry =
    response.status === 401 && !options.skipAuth && options.retryOnUnauthorized !== false

  if (shouldRetry) {
    const newAccessToken = await tokenManager.refresh(refreshTokens)
    if (newAccessToken) {
      response = await performFetch(path, options)
    }
  }

  if (!response.ok) {
    const detail = await parseErrorBody(response)
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
