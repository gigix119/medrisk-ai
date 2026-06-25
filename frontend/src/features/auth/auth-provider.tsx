import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useEffect, useState } from 'react'

import { refreshTokens } from '@/api/client'
import { tokenManager } from '@/api/token-manager'
import { queryKeys } from '@/app/query-client'

import { authApi, type LoginInput, type RegisterRequest } from './api'
import { AuthContext, type AuthContextValue } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [hasSession, setHasSession] = useState(false)
  // A refresh token surviving in sessionStorage means a reload happened mid-session; the
  // mount effect below silently restores it instead of bouncing the user to /login.
  const [isInitializing, setIsInitializing] = useState(() =>
    Boolean(tokenManager.getRefreshToken()),
  )

  const { data: user = null } = useQuery({
    queryKey: queryKeys.authMe,
    queryFn: authApi.me,
    enabled: hasSession,
    staleTime: 60_000,
  })

  const logout = useCallback(async () => {
    const refreshToken = tokenManager.getRefreshToken()
    tokenManager.clear()
    setHasSession(false)
    queryClient.clear()
    if (refreshToken) {
      await authApi.logout(refreshToken).catch(() => {
        // Best-effort: the session is already cleared client-side either way.
      })
    }
  }, [queryClient])

  useEffect(() => {
    return tokenManager.onForcedLogout(() => {
      setHasSession(false)
      queryClient.clear()
    })
  }, [queryClient])

  useEffect(() => {
    if (!tokenManager.getRefreshToken()) return

    tokenManager
      .refresh(refreshTokens)
      .then((accessToken) => setHasSession(accessToken !== null))
      .finally(() => setIsInitializing(false))
  }, [])

  const login = useCallback(
    async (input: LoginInput) => {
      const tokens = await authApi.login(input)
      tokenManager.setSession({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      })
      setHasSession(true)
      await queryClient.invalidateQueries({ queryKey: queryKeys.authMe })
    },
    [queryClient],
  )

  const register = useCallback(async (input: RegisterRequest) => {
    await authApi.register(input)
  }, [])

  const value: AuthContextValue = {
    user,
    isAuthenticated: hasSession,
    isInitializing,
    login,
    register,
    logout,
  }

  return <AuthContext value={value}>{children}</AuthContext>
}
