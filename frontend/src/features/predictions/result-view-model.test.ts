import { describe, expect, it } from 'vitest'

import { MOCK_ACTIVE_MODEL, MOCK_PREDICTION_READ, MOCK_PREDICTION_RESPONSE } from '@/test/handlers'

import { fromHistoryRead, fromRichResult } from './result-view-model'

describe('fromRichResult', () => {
  it('derives both class probabilities from calibrated_probability and positive_class', () => {
    const viewModel = fromRichResult(MOCK_PREDICTION_RESPONSE, MOCK_ACTIVE_MODEL.class_names, {
      kind: 'not-stored',
    })

    expect(viewModel.classProbabilities).toEqual([
      { label: 'normal', probability: 0.88, isPredicted: true },
      { label: 'tumor', probability: 0.12, isPredicted: false },
    ])
  })

  it('maps an available Grad-CAM explanation to a data URL', () => {
    const viewModel = fromRichResult(MOCK_PREDICTION_RESPONSE, MOCK_ACTIVE_MODEL.class_names, {
      kind: 'not-stored',
    })

    expect(viewModel.gradCam).toMatchObject({ kind: 'available' })
    if (viewModel.gradCam.kind === 'available') {
      expect(viewModel.gradCam.dataUrl).toContain('data:image/png;base64,')
    }
  })

  it('reports a missing positive class as no breakdown rather than guessing', () => {
    const responseWithoutPositiveClass = { ...MOCK_PREDICTION_RESPONSE, positive_class: '' }
    const viewModel = fromRichResult(responseWithoutPositiveClass, MOCK_ACTIVE_MODEL.class_names, {
      kind: 'not-stored',
    })

    expect(viewModel.classProbabilities).toBeNull()
  })
})

describe('fromHistoryRead', () => {
  it('derives class probabilities when the prediction model version matches the active model', () => {
    const viewModel = fromHistoryRead(MOCK_PREDICTION_READ, MOCK_ACTIVE_MODEL)

    expect(viewModel.classProbabilities).toEqual([
      { label: 'normal', probability: 0.88, isPredicted: true },
      { label: 'tumor', probability: 0.12, isPredicted: false },
    ])
    expect(viewModel.syntheticOnly).toBe(true)
  })

  it('falls back to no breakdown and unknown synthetic status when the model version no longer matches', () => {
    const retiredModel = { ...MOCK_ACTIVE_MODEL, version: 'some-other-version' }
    const viewModel = fromHistoryRead(MOCK_PREDICTION_READ, retiredModel)

    expect(viewModel.classProbabilities).toBeNull()
    expect(viewModel.syntheticOnly).toBeNull()
  })

  it('never reports Grad-CAM as available - explanations are never persisted', () => {
    const viewModel = fromHistoryRead(MOCK_PREDICTION_READ, MOCK_ACTIVE_MODEL)

    expect(viewModel.gradCam).toEqual({ kind: 'unavailable', reason: 'never_persisted' })
  })

  it('reports the original image as not stored', () => {
    const viewModel = fromHistoryRead(MOCK_PREDICTION_READ, MOCK_ACTIVE_MODEL)

    expect(viewModel.image).toEqual({ kind: 'not-stored' })
  })
})
