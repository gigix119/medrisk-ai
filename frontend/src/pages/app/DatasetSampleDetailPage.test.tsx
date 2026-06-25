import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { routes } from '@/config/routes'
import { renderWithProviders } from '@/test/render'
import {
  MOCK_DATASET_ID,
  MOCK_DATASET_SAMPLE_CORRECT,
  MOCK_DATASET_SAMPLE_INCORRECT,
  MOCK_SAMPLE_ID_CORRECT,
  MOCK_SAMPLE_ID_INCORRECT,
} from '@/test/handlers'

import { DatasetSampleDetailPage } from './DatasetSampleDetailPage'
import { PredictionResultPage } from './PredictionResultPage'

function renderSampleFlow(datasetId: string, sampleId: string) {
  return renderWithProviders(
    <Routes>
      <Route
        path={routes.datasetSampleDetail(':datasetId', ':sampleId')}
        element={<DatasetSampleDetailPage />}
      />
      <Route path={routes.predictionDetail(':predictionId')} element={<PredictionResultPage />} />
    </Routes>,
    { initialEntries: [routes.datasetSampleDetail(datasetId, sampleId)] },
  )
}

describe('DatasetSampleDetailPage', () => {
  it("renders the sample's ground truth, split, dimensions and checksum before running inference", async () => {
    renderSampleFlow(MOCK_DATASET_ID, MOCK_SAMPLE_ID_CORRECT)

    expect(
      await screen.findByText(MOCK_DATASET_SAMPLE_CORRECT.ground_truth_label),
    ).toBeInTheDocument()
    expect(screen.getByText(MOCK_DATASET_SAMPLE_CORRECT.split)).toBeInTheDocument()
    expect(screen.getAllByText('96×96').length).toBeGreaterThanOrEqual(1)
    expect(
      screen.getByText(`${MOCK_DATASET_SAMPLE_CORRECT.checksum_sha256.slice(0, 16)}…`),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run inference/i })).toBeInTheDocument()
  })

  it('runs inference and shows a correct-match ground truth comparison on the result page', async () => {
    renderSampleFlow(MOCK_DATASET_ID, MOCK_SAMPLE_ID_CORRECT)

    const runButton = await screen.findByRole('button', { name: /run inference/i })
    await userEvent.setup().click(runButton)

    expect(await screen.findByText('Correct prediction')).toBeInTheDocument()
    expect(screen.getByText('Ground truth comparison')).toBeInTheDocument()
  })

  it('runs inference and shows an incorrect-match comparison with error analysis on the result page', async () => {
    renderSampleFlow(MOCK_DATASET_ID, MOCK_SAMPLE_ID_INCORRECT)
    expect(
      await screen.findByText(MOCK_DATASET_SAMPLE_INCORRECT.ground_truth_label),
    ).toBeInTheDocument()

    const runButton = screen.getByRole('button', { name: /run inference/i })
    await userEvent.setup().click(runButton)

    expect(await screen.findByText('Incorrect prediction')).toBeInTheDocument()
    expect(screen.getByText('Error analysis')).toBeInTheDocument()
  })

  it('shows a friendly not-found state for an unknown sample id', async () => {
    renderSampleFlow(MOCK_DATASET_ID, '99999999-9999-9999-9999-999999999999')

    expect(await screen.findByText('Sample not found.')).toBeInTheDocument()
  })
})
