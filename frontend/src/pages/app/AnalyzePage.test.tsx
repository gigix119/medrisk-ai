import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { routes } from '@/config/routes'
import { renderWithProviders } from '@/test/render'
import { server } from '@/test/server'

import { AnalyzePage } from './AnalyzePage'
import { PredictionResultPage } from './PredictionResultPage'

const API_BASE = 'http://localhost:8000'

function renderAnalyzeFlow() {
  return renderWithProviders(
    <Routes>
      <Route path={routes.analyze} element={<AnalyzePage />} />
      <Route path={routes.predictionDetail(':predictionId')} element={<PredictionResultPage />} />
    </Routes>,
    { initialEntries: [routes.analyze] },
  )
}

function mockDecodableBitmap(width: number, height: number) {
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => ({ width, height, close: vi.fn() })),
  )
}

async function selectFile(name: string, type: string) {
  // fireEvent.change bypasses the file input's `accept` filtering that userEvent.upload
  // applies - the dropzone also accepts drag-and-drop, which isn't constrained by `accept`,
  // so the app's own validation (not just the OS file picker) must catch a mismatched type.
  const file = new File([new Uint8Array(10)], name, { type })
  const input = await screen.findByLabelText(/choose an image file/i)
  fireEvent.change(input, { target: { files: [file] } })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AnalyzePage', () => {
  it('walks a valid image through confirm and submit to the result page', async () => {
    mockDecodableBitmap(96, 96)
    renderAnalyzeFlow()
    await selectFile('sample-patch-96x96.png', 'image/png')

    const analyzeButton = await screen.findByRole('button', { name: /analyze image/i })
    await userEvent.setup().click(analyzeButton)

    expect(await screen.findByText(/model output: normal/i)).toBeInTheDocument()
  })

  it('rejects an unsupported file type before allowing analysis', async () => {
    renderAnalyzeFlow()
    await selectFile('patch.gif', 'image/gif')

    expect(await screen.findByText(/only png and jpeg images are supported/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /analyze image/i })).not.toBeInTheDocument()
  })

  it('rejects an image whose dimensions do not match the model input contract', async () => {
    mockDecodableBitmap(50, 50)
    renderAnalyzeFlow()
    await selectFile('patch.png', 'image/png')

    expect(await screen.findByText(/model requires exactly 96 × 96/i)).toBeInTheDocument()
  })

  it('disables the analyze button immediately after submitting to prevent a double submission', async () => {
    server.use(
      http.post(`${API_BASE}/api/v1/predictions/histopathology`, async () => {
        await delay(50)
        return HttpResponse.json({ prediction_id: 'unused' }, { status: 201 })
      }),
    )
    mockDecodableBitmap(96, 96)
    renderAnalyzeFlow()
    await selectFile('sample-patch-96x96.png', 'image/png')

    const analyzeButton = await screen.findByRole('button', { name: /analyze image/i })
    await userEvent.setup().click(analyzeButton)

    expect(analyzeButton).toBeDisabled()
  })
})
