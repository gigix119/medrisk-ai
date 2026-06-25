import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { MOCK_DATASET } from '@/test/handlers'

import { DatasetExplorerPage } from './DatasetExplorerPage'

describe('DatasetExplorerPage', () => {
  it('lists the available datasets with their synthetic/public badges', async () => {
    renderWithProviders(<DatasetExplorerPage />)

    expect(await screen.findByText(MOCK_DATASET.name)).toBeInTheDocument()
    expect(screen.getByText('Synthetic')).toBeInTheDocument()
    expect(screen.getByText('Public')).toBeInTheDocument()
  })

  it('links each dataset card to its detail page rather than any upload control', async () => {
    renderWithProviders(<DatasetExplorerPage />)

    const link = await screen.findByRole('link', { name: new RegExp(MOCK_DATASET.name) })
    expect(link).toHaveAttribute('href', `/app/datasets/${MOCK_DATASET.id}`)
    expect(screen.queryByLabelText(/choose an image file/i)).not.toBeInTheDocument()
  })
})
