import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '@/test/render'
import { MOCK_EVALUATION_RUN_COMPLETED, MOCK_EVALUATION_RUN_PENDING } from '@/test/handlers'

import { ResearchOverviewPage } from './ResearchOverviewPage'

describe('ResearchOverviewPage', () => {
  it('lists both the completed and the pending evaluation run', async () => {
    renderWithProviders(<ResearchOverviewPage />)

    expect(await screen.findAllByText(/smoke-baseline-cnn/)).toHaveLength(2)
    expect(screen.getByText('Completed', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('Pending', { selector: 'span' })).toBeInTheDocument()
  })

  it('shows the primary metric for the completed run and the empty placeholder for the pending one', async () => {
    renderWithProviders(<ResearchOverviewPage />)

    await screen.findAllByText(/smoke-baseline-cnn/)
    expect(screen.getByText(/accuracy: 0.5/)).toBeInTheDocument()
    expect(screen.getByText('No primary metric recorded yet')).toBeInTheDocument()
  })

  it('links each run to its results page', async () => {
    renderWithProviders(<ResearchOverviewPage />)

    const links = await screen.findAllByRole('link')
    const hrefs = links.map((link) => link.getAttribute('href'))
    expect(hrefs).toContain(`/app/research/${MOCK_EVALUATION_RUN_COMPLETED.id}`)
    expect(hrefs).toContain(`/app/research/${MOCK_EVALUATION_RUN_PENDING.id}`)
  })
})
