import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { routes } from '@/config/routes'
import { renderWithProviders } from '@/test/render'
import { MOCK_DATASET, MOCK_DATASET_ID } from '@/test/handlers'

import { DatasetDetailPage } from './DatasetDetailPage'

function renderDetailPage(datasetId: string) {
  return renderWithProviders(
    <Routes>
      <Route path={routes.datasetDetail(':datasetId')} element={<DatasetDetailPage />} />
    </Routes>,
    { initialEntries: [routes.datasetDetail(datasetId)] },
  )
}

describe('DatasetDetailPage', () => {
  it('renders dataset overview, intended use and source metadata', async () => {
    renderDetailPage(MOCK_DATASET_ID)

    expect(await screen.findByRole('heading', { name: MOCK_DATASET.name })).toBeInTheDocument()
    expect(screen.getByText(MOCK_DATASET.description)).toBeInTheDocument()
    expect(screen.getByText(MOCK_DATASET.intended_use)).toBeInTheDocument()
    expect(screen.getByText(MOCK_DATASET.prohibited_use)).toBeInTheDocument()
    expect(screen.getByText(MOCK_DATASET.source_name)).toBeInTheDocument()
    expect(screen.getByText(MOCK_DATASET.license_name)).toBeInTheDocument()
  })

  it('lists both samples in the browser, each linking to its own sample detail page', async () => {
    renderDetailPage(MOCK_DATASET_ID)

    const normalLabels = await screen.findAllByText('normal')
    const tumorLabels = await screen.findAllByText('tumor')
    expect(normalLabels.length).toBeGreaterThan(0)
    expect(tumorLabels.length).toBeGreaterThan(0)
  })

  it('filters samples down to the matching class when a class filter is selected', async () => {
    renderDetailPage(MOCK_DATASET_ID)
    await screen.findByText('normal', { selector: 'span' })

    const classSelect = screen.getByLabelText('Class')
    await userEvent.setup().selectOptions(classSelect, 'tumor')

    expect(await screen.findByText('tumor', { selector: 'span' })).toBeInTheDocument()
    expect(screen.queryByText('normal', { selector: 'span' })).not.toBeInTheDocument()
  })

  it('shows a not-found state for an unknown dataset id', async () => {
    renderDetailPage('99999999-9999-9999-9999-999999999999')

    expect(await screen.findByText('Dataset not found.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to datasets/i })).toBeInTheDocument()
  })
})
