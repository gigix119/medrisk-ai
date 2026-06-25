import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { VALID_CREDENTIALS } from '@/test/handlers'

import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
  it('shows a validation error when submitted empty', async () => {
    renderWithProviders(<LoginPage />)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /log in/i }))

    expect(await screen.findByText(/valid email address/i)).toBeInTheDocument()
  })

  it('shows a generic error for invalid credentials', async () => {
    renderWithProviders(<LoginPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText(/email/i), 'wrong@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'wrong-password')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    expect(await screen.findByText(/incorrect email or password/i)).toBeInTheDocument()
  })

  it('logs in successfully with valid credentials', async () => {
    renderWithProviders(<LoginPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText(/email/i), VALID_CREDENTIALS.email)
    await user.type(screen.getByLabelText(/^password$/i), VALID_CREDENTIALS.password)
    await user.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(screen.queryByText(/incorrect email or password/i)).not.toBeInTheDocument()
    })
  })
})
