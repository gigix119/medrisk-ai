import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { routes } from '@/config/routes'
import { renderWithProviders } from '@/test/render'
import {
  MOCK_DATASET_ID,
  MOCK_PREDICT_ON_SAMPLE_RESPONSE,
  MOCK_PREDICT_ON_SAMPLE_RESPONSE_INCORRECT,
  MOCK_PREDICTION_ID,
  MOCK_SAMPLE_ID_CORRECT,
  MOCK_SAMPLE_ID_INCORRECT,
} from '@/test/handlers'

import { PredictionResultPage } from './PredictionResultPage'

function renderResultPage(predictionId: string) {
  return renderWithProviders(
    <Routes>
      <Route path={routes.predictionDetail(':predictionId')} element={<PredictionResultPage />} />
    </Routes>,
    { initialEntries: [routes.predictionDetail(predictionId)] },
  )
}

function renderSampleResultPage(
  sampleResult: typeof MOCK_PREDICT_ON_SAMPLE_RESPONSE,
  sampleId: string,
) {
  return renderWithProviders(
    <Routes>
      <Route path={routes.predictionDetail(':predictionId')} element={<PredictionResultPage />} />
    </Routes>,
    {
      initialEntries: [
        {
          pathname: routes.predictionDetail(sampleResult.prediction_id),
          state: { sampleResult, datasetId: MOCK_DATASET_ID, sampleId },
        },
      ],
    },
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

describe('PredictionResultPage (fresh dataset-sample result, in-memory state)', () => {
  it('renders a correct-match ground truth comparison and the "run another sample" CTA', async () => {
    renderSampleResultPage(MOCK_PREDICT_ON_SAMPLE_RESPONSE, MOCK_SAMPLE_ID_CORRECT)

    expect(await screen.findByText('Ground truth comparison')).toBeInTheDocument()
    expect(screen.getByText('Correct prediction')).toBeInTheDocument()
    expect(screen.queryByText('Error analysis')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run another sample/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /analyze another image/i })).not.toBeInTheDocument()
  })

  it('renders an incorrect-match comparison with error analysis', async () => {
    renderSampleResultPage(MOCK_PREDICT_ON_SAMPLE_RESPONSE_INCORRECT, MOCK_SAMPLE_ID_INCORRECT)

    expect(await screen.findByText('Incorrect prediction')).toBeInTheDocument()
    expect(screen.getByText('Error analysis')).toBeInTheDocument()
  })

  it('shows the Grad-CAM explanation returned with the sample result', async () => {
    renderSampleResultPage(MOCK_PREDICT_ON_SAMPLE_RESPONSE, MOCK_SAMPLE_ID_CORRECT)

    expect(await screen.findByText('Visual explanation (Grad-CAM)')).toBeInTheDocument()
  })

  it('exposes the reproducibility details (dataset, version, sample id, split)', async () => {
    renderSampleResultPage(MOCK_PREDICT_ON_SAMPLE_RESPONSE, MOCK_SAMPLE_ID_CORRECT)

    expect(await screen.findByText('Reproducibility details')).toBeInTheDocument()
    expect(screen.getByText(MOCK_PREDICT_ON_SAMPLE_RESPONSE.dataset_name)).toBeInTheDocument()
    expect(screen.getByText(MOCK_PREDICT_ON_SAMPLE_RESPONSE.dataset_version)).toBeInTheDocument()
  })
})
