import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { routes } from '@/config/routes'
import { renderWithProviders } from '@/test/render'
import { MOCK_PREDICTION_ID } from '@/test/handlers'

import { PredictionResultPage } from './PredictionResultPage'

function renderResultPage(predictionId: string) {
  return renderWithProviders(
    <Routes>
      <Route path={routes.predictionDetail(':predictionId')} element={<PredictionResultPage />} />
    </Routes>,
    { initialEntries: [routes.predictionDetail(predictionId)] },
  )
}

describe('PredictionResultPage (loaded by id, no fresh in-memory result)', () => {
  it('renders the decision, predicted class and probability breakdown from the history endpoint', async () => {
    renderResultPage(MOCK_PREDICTION_ID)

    expect(await screen.findByText(/model output: normal/i)).toBeInTheDocument()
    expect(screen.getByText('Negative')).toBeInTheDocument()
    expect(screen.getByText('normal')).toBeInTheDocument()
    expect(screen.getByText('tumor')).toBeInTheDocument()
    expect(screen.getByText('88.0%')).toBeInTheDocument()
    expect(screen.getByText('12.0%')).toBeInTheDocument()
  })

  it('explains that the original image is not stored outside the immediate analysis', async () => {
    renderResultPage(MOCK_PREDICTION_ID)

    expect(await screen.findByText(/original image is not stored/i)).toBeInTheDocument()
  })

  it('explains that Grad-CAM is unavailable because it is never persisted', async () => {
    renderResultPage(MOCK_PREDICTION_ID)

    expect(
      await screen.findByText(/visual explanations are only available immediately/i),
    ).toBeInTheDocument()
  })

  it('surfaces the synthetic-model notice', async () => {
    renderResultPage(MOCK_PREDICTION_ID)

    expect(await screen.findByText(/synthetic test model/i)).toBeInTheDocument()
  })

  it('shows a friendly not-found state for an unknown prediction id', async () => {
    renderResultPage('99999999-9999-9999-9999-999999999999')

    expect(await screen.findByText(/analysis not found/i)).toBeInTheDocument()
  })
})
