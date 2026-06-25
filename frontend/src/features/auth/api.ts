import { apiRequest } from '@/api/client'
import type { components } from '@/api/generated/schema'

export type UserRead = components['schemas']['UserRead']
export type TokenResponse = components['schemas']['TokenResponse']
export type RegisterRequest = components['schemas']['RegisterRequest']

export interface LoginInput {
  email: string
  password: string
}

export const authApi = {
  register(input: RegisterRequest): Promise<UserRead> {
    return apiRequest<UserRead>('/api/v1/auth/register', {
      method: 'POST',
      body: input,
      skipAuth: true,
    })
  },

  login({ email, password }: LoginInput): Promise<TokenResponse> {
    const body = new URLSearchParams({ grant_type: 'password', username: email, password })
    return apiRequest<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      rawBody: body,
      skipAuth: true,
    })
  },

  logout(refreshToken: string): Promise<void> {
    return apiRequest<void>('/api/v1/auth/logout', {
      method: 'POST',
      body: { refresh_token: refreshToken },
      skipAuth: true,
    })
  },

  me(): Promise<UserRead> {
    return apiRequest<UserRead>('/api/v1/users/me')
  },
}
