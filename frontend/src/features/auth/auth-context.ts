import { createContext } from 'react'

import type { LoginInput, RegisterRequest, UserRead } from './api'

export interface AuthContextValue {
  user: UserRead | null
  isAuthenticated: boolean
  isInitializing: boolean
  login: (input: LoginInput) => Promise<void>
  register: (input: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
