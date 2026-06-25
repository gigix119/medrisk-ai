import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { BrowserRouter } from 'react-router-dom'

import { AccessibilityPreferencesProvider } from '@/features/accessibility-preferences/accessibility-preferences-provider'
import { AuthProvider } from '@/features/auth/auth-provider'

import { ErrorBoundary } from './error-boundary'
import { queryClient } from './query-client'

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AccessibilityPreferencesProvider>
          <BrowserRouter>
            <AuthProvider>{children}</AuthProvider>
          </BrowserRouter>
        </AccessibilityPreferencesProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
