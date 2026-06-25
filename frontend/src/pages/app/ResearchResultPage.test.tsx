import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { routes } from '@/config/routes'
import { renderWithProviders } from '@/test/render'
import { MOCK_EVALUATION_ID_COMPLETED, MOCK_EVALUATION_ID_PENDING } from '@/test/handlers'

import { ResearchResultPage } from './ResearchResultPage'

function renderResultPage(evaluationId: string) {
  return renderWithProviders(
    <Routes>
      <Route path={routes.researchResult(':evaluationId')} element={<ResearchResultPage />} />
    </Routes>,
    { initialEntries: [routes.researchResult(evaluationId)] },
  )
}

describe('ResearchResultPage', () => {
  it('renders run details, metrics (including an undefined one) and the confusion matrix for a completed run', async () => {
    renderResultPage(MOCK_EVALUATION_ID_COMPLETED)

    expect(await screen.findByRole('heading', { name: /smoke-baseline-cnn/ })).toBeInTheDocument()
    expect(screen.getByText('Completed at')).toBeInTheDocument()
    expect(screen.getByText('Synthetic demonstration')).toBeInTheDocument()

    // Metrics: an "ok" metric renders its value, an "undefined" one renders its status, never 0.
    expect(await screen.findByText('accuracy')).toBeInTheDocument()
    expect(screen.getByText(/0\.5/)).toBeInTheDocument()
    expect(screen.getByText('roc auc')).toBeInTheDocument()
    expect(screen.getByText('Undefined')).toBeInTheDocument()

    // Confusion matrix
    expect(await screen.findByText('Confusion matrix')).toBeInTheDocument()
    expect(screen.getAllByText('normal').length).toBeGreaterThan(0)
    expect(screen.getAllByText('tumor').length).toBeGreaterThan(0)
  })

  it('lists per-sample predictions and filters them by correctness', async () => {
    renderResultPage(MOCK_EVALUATION_ID_COMPLETED)
    await screen.findByText('Confusion matrix')

    expect(screen.getByText('train-0000')).toBeInTheDocument()
    expect(screen.getByText('train-0001')).toBeInTheDocument()

    const filter = screen.getByLabelText('Correctness')
    await userEvent.setup().selectOptions(filter, 'incorrect')

    expect(await screen.findByText('train-0001')).toBeInTheDocument()
    expect(screen.queryByText('train-0000')).not.toBeInTheDocument()
  })

  it('shows a no-metrics-yet message for a pending run, without a confusion matrix', async () => {
    renderResultPage(MOCK_EVALUATION_ID_PENDING)

    expect(await screen.findByText('Pending')).toBeInTheDocument()
    expect(screen.getByText('This run has no completed metrics yet.')).toBeInTheDocument()
    expect(screen.queryByText('Confusion matrix')).not.toBeInTheDocument()
  })

  it('shows a not-found state for an unknown evaluation id', async () => {
    renderResultPage('00000000-0000-0000-0000-000000000000')

    expect(await screen.findByText('Evaluation run not found.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to evaluation results/i })).toBeInTheDocument()
  })
})
