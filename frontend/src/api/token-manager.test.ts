import { beforeEach, describe, expect, it, vi } from 'vitest'

import { tokenManager } from './token-manager'

describe('tokenManager', () => {
  beforeEach(() => {
    tokenManager.clear()
  })

  it('has no access token until a session is set', () => {
    expect(tokenManager.getAccessToken()).toBeNull()
  })

  it('stores the access token in memory and the refresh token in sessionStorage', () => {
    tokenManager.setSession({ accessToken: 'access-1', refreshToken: 'refresh-1' })

    expect(tokenManager.getAccessToken()).toBe('access-1')
    expect(tokenManager.getRefreshToken()).toBe('refresh-1')
  })

  it('clears both tokens on logout', () => {
    tokenManager.setSession({ accessToken: 'access-1', refreshToken: 'refresh-1' })
    tokenManager.clear()

    expect(tokenManager.getAccessToken()).toBeNull()
    expect(tokenManager.getRefreshToken()).toBeNull()
  })

  it('returns null and does not call the refresh function when there is no refresh token', async () => {
    const refreshFn = vi.fn()

    const result = await tokenManager.refresh(refreshFn)

    expect(result).toBeNull()
    expect(refreshFn).not.toHaveBeenCalled()
  })

  it('deduplicates concurrent refresh calls into a single network request', async () => {
    tokenManager.setSession({ accessToken: 'stale', refreshToken: 'refresh-1' })
    let resolveRefresh: (value: { accessToken: string; refreshToken: string }) => void = () => {}
    const refreshFn = vi.fn(
      () =>
        new Promise<{ accessToken: string; refreshToken: string }>((resolve) => {
          resolveRefresh = resolve
        }),
    )

    const first = tokenManager.refresh(refreshFn)
    const second = tokenManager.refresh(refreshFn)
    resolveRefresh({ accessToken: 'fresh-access', refreshToken: 'fresh-refresh' })

    const [firstResult, secondResult] = await Promise.all([first, second])

    expect(refreshFn).toHaveBeenCalledTimes(1)
    expect(firstResult).toBe('fresh-access')
    expect(secondResult).toBe('fresh-access')
    expect(tokenManager.getAccessToken()).toBe('fresh-access')
  })

  it('clears the session and notifies listeners when refresh fails', async () => {
    tokenManager.setSession({ accessToken: 'stale', refreshToken: 'refresh-1' })
    const listener = vi.fn()
    tokenManager.onForcedLogout(listener)
    const refreshFn = vi.fn().mockRejectedValue(new Error('refresh token revoked'))

    const result = await tokenManager.refresh(refreshFn)

    expect(result).toBeNull()
    expect(tokenManager.getAccessToken()).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
  })
})
