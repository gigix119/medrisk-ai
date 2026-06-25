import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { tokenManager } from '@/api/token-manager'
import { AuthProvider } from '@/features/auth/auth-provider'

import { ProtectedRoute } from './ProtectedRoute'

function renderApp(initialEntries: string[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login page</div>} />
            <Route
              path="/app"
              element={
                <ProtectedRoute>
                  <div>Protected dashboard</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProtectedRoute', () => {
  it('redirects to /login when there is no session', async () => {
    renderApp(['/app'])

    expect(await screen.findByText('Login page')).toBeInTheDocument()
  })

  it('renders the protected content when a session is restored from sessionStorage', async () => {
    tokenManager.setSession({ accessToken: 'access-1', refreshToken: 'mock-refresh-token' })

    renderApp(['/app'])

    expect(await screen.findByText('Protected dashboard')).toBeInTheDocument()
  })
})
