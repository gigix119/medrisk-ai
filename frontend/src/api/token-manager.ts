/**
 * Access token lives in memory only (never localStorage, never logged). The refresh token
 * lives in sessionStorage so a reload survives but closing the tab doesn't persist a
 * long-lived credential indefinitely. The backend issues plain bearer tokens (no HttpOnly
 * cookie support), so this in-memory + sessionStorage split is the documented fallback
 * strategy, not the preferred one.
 */
const REFRESH_TOKEN_KEY = 'medrisk.refresh_token'

type RefreshFn = (refreshToken: string) => Promise<{ accessToken: string; refreshToken: string }>

let accessToken: string | null = null
let refreshInFlight: Promise<string | null> | null = null
const forcedLogoutListeners = new Set<() => void>()

export const tokenManager = {
  getAccessToken(): string | null {
    return accessToken
  },

  setSession(tokens: { accessToken: string; refreshToken: string }): void {
    accessToken = tokens.accessToken
    sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken)
  },

  getRefreshToken(): string | null {
    return sessionStorage.getItem(REFRESH_TOKEN_KEY)
  },

  clear(): void {
    accessToken = null
    sessionStorage.removeItem(REFRESH_TOKEN_KEY)
  },

  onForcedLogout(listener: () => void): () => void {
    forcedLogoutListeners.add(listener)
    return () => forcedLogoutListeners.delete(listener)
  },

  /** Deduplicates concurrent refresh attempts so two failed requests don't each rotate the
   * refresh token (the backend revokes the old one on rotation, so the second call would
   * otherwise fail with TOKEN_REVOKED). */
  async refresh(refreshFn: RefreshFn): Promise<string | null> {
    if (refreshInFlight) return refreshInFlight

    const currentRefreshToken = tokenManager.getRefreshToken()
    if (!currentRefreshToken) return null

    refreshInFlight = refreshFn(currentRefreshToken)
      .then((tokens) => {
        tokenManager.setSession(tokens)
        return tokens.accessToken
      })
      .catch(() => {
        tokenManager.clear()
        forcedLogoutListeners.forEach((listener) => listener())
        return null
      })
      .finally(() => {
        refreshInFlight = null
      })

    return refreshInFlight
  },
}
