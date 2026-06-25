import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { MOCK_DATASET } from '@/test/handlers'

import { AnalyzePage } from './AnalyzePage'

describe('AnalyzePage', () => {
  it('is a dataset-grid entry point with no upload control reachable', async () => {
    renderWithProviders(<AnalyzePage />)

    expect(await screen.findByText(MOCK_DATASET.name)).toBeInTheDocument()
    expect(screen.queryByLabelText(/choose an image file/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /analyze image/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/drag and drop an image/i)).not.toBeInTheDocument()
  })

  it('links each dataset card to its detail page', async () => {
    renderWithProviders(<AnalyzePage />)

    const link = await screen.findByRole('link', { name: new RegExp(MOCK_DATASET.name) })
    expect(link).toHaveAttribute('href', `/app/datasets/${MOCK_DATASET.id}`)
  })
})
