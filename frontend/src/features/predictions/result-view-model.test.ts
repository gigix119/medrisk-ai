import { describe, expect, it } from 'vitest'

import {
  MOCK_ACTIVE_MODEL,
  MOCK_PREDICT_ON_SAMPLE_RESPONSE,
  MOCK_PREDICT_ON_SAMPLE_RESPONSE_INCORRECT,
  MOCK_PREDICTION_READ,
  MOCK_PREDICTION_RESPONSE,
} from '@/test/handlers'

import { fromHistoryRead, fromRichResult, fromSampleResult } from './result-view-model'

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

  it('never attaches ground truth - the upload flow has no known label', () => {
    const viewModel = fromRichResult(MOCK_PREDICTION_RESPONSE, MOCK_ACTIVE_MODEL.class_names, {
      kind: 'not-stored',
    })

    expect(viewModel.groundTruth).toBeNull()
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

  it('reports no ground truth for a legacy (upload-based) prediction', () => {
    const viewModel = fromHistoryRead(MOCK_PREDICTION_READ, MOCK_ACTIVE_MODEL)

    expect(viewModel.groundTruth).toBeNull()
  })

  it('reports partial ground truth for a dataset-based historical read, never fabricating the missing display fields', () => {
    const datasetBackedRead = {
      ...MOCK_PREDICTION_READ,
      dataset_id: '33333333-3333-3333-3333-333333333333',
      split: 'train',
      ground_truth_label: 'normal',
      is_correct: true,
    }
    const viewModel = fromHistoryRead(datasetBackedRead, MOCK_ACTIVE_MODEL)

    expect(viewModel.groundTruth).toEqual({
      label: 'normal',
      predictedLabel: 'normal',
      isCorrect: true,
      datasetId: '33333333-3333-3333-3333-333333333333',
      datasetName: null,
      datasetVersion: null,
      sampleKey: null,
      split: 'train',
    })
  })
})

describe('fromSampleResult', () => {
  it('builds a full ground truth view model, including reproducibility fields, for a correct prediction', () => {
    const viewModel = fromSampleResult(
      MOCK_PREDICT_ON_SAMPLE_RESPONSE,
      MOCK_ACTIVE_MODEL.class_names,
      { kind: 'not-stored' },
    )

    expect(viewModel.groundTruth).toEqual({
      label: 'normal',
      predictedLabel: 'normal',
      isCorrect: true,
      datasetId: MOCK_PREDICT_ON_SAMPLE_RESPONSE.dataset_id,
      datasetName: MOCK_PREDICT_ON_SAMPLE_RESPONSE.dataset_name,
      datasetVersion: MOCK_PREDICT_ON_SAMPLE_RESPONSE.dataset_version,
      sampleKey: MOCK_PREDICT_ON_SAMPLE_RESPONSE.sample_key,
      split: MOCK_PREDICT_ON_SAMPLE_RESPONSE.split,
    })
  })

  it('reports isCorrect as false when the predicted class does not match the ground truth', () => {
    const viewModel = fromSampleResult(
      MOCK_PREDICT_ON_SAMPLE_RESPONSE_INCORRECT,
      MOCK_ACTIVE_MODEL.class_names,
      { kind: 'not-stored' },
    )

    expect(viewModel.groundTruth).toMatchObject({
      label: 'tumor',
      predictedLabel: 'normal',
      isCorrect: false,
    })
  })
})
