import { http, HttpResponse } from 'msw'

import type { ActiveModelResponse } from '@/features/model/api'
import type { HistopathologyPredictionResponse, PredictionRead } from '@/features/predictions/api'

const API_BASE = 'http://localhost:8000'

export const VALID_CREDENTIALS = { email: 'researcher@example.com', password: 'correct-password' }

const MOCK_USER = {
  id: '11111111-1111-1111-1111-111111111111',
  email: VALID_CREDENTIALS.email,
  full_name: 'Ada Researcher',
  is_active: true,
  is_superuser: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function tokenResponse() {
  return {
    access_token: 'mock-access-token',
    refresh_token: 'mock-refresh-token',
    token_type: 'bearer',
    expires_in: 900,
  }
}

export const MOCK_PREDICTION_ID = '22222222-2222-2222-2222-222222222222'

/** A real, valid, minimal 1x1 PNG - enough to satisfy <img src> and base64 decoding in tests. */
export const TINY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='

export const MOCK_ACTIVE_MODEL: ActiveModelResponse = {
  module: 'histopathology',
  model_id: 'smoke-baseline-cnn',
  model_name: 'Smoke Baseline CNN',
  version: '0.0.1-smoke',
  architecture: 'baseline_cnn',
  dataset_name: 'synthetic',
  dataset_mode: 'synthetic',
  synthetic_only: true,
  eligible_for_demo: false,
  input_contract: { input_height: 96, input_width: 96, input_channels: 3 },
  class_names: ['normal', 'tumor'] as [string, string],
  positive_class: 'tumor',
  threshold: 0.5,
  review_policy: { negative_probability_max: 0.3, positive_probability_min: 0.7 },
  calibration_enabled: true,
  activated_at: '2026-01-01T00:00:00Z',
  disclaimer: 'This software is an educational and research portfolio project.',
}

export const MOCK_PREDICTION_RESPONSE: HistopathologyPredictionResponse = {
  prediction_id: MOCK_PREDICTION_ID,
  module: 'histopathology',
  status: 'completed',
  decision: 'negative',
  predicted_class: 'normal',
  raw_probability: 0.12,
  calibrated_probability: 0.12,
  predicted_class_probability: 0.88,
  confidence_score: 0.88,
  positive_class: 'tumor',
  threshold: 0.5,
  review_policy: { negative_probability_max: 0.3, positive_probability_min: 0.7 },
  input: {
    sha256: 'a'.repeat(64),
    format: 'PNG',
    mime_type: 'image/png',
    size_bytes: 18136,
    original_width: 96,
    original_height: 96,
    processed_width: 96,
    processed_height: 96,
  },
  model: {
    model_id: 'smoke-baseline-cnn',
    model_name: 'Smoke Baseline CNN',
    version: '0.0.1-smoke',
    architecture: 'baseline_cnn',
    synthetic_only: true,
    eligible_for_demo: false,
  },
  timings: {
    validation_ms: 1.1,
    preprocessing_ms: 0.8,
    inference_ms: 5.2,
    calibration_ms: 0.1,
    explanation_ms: 12.3,
    total_ms: 19.5,
  },
  explanation: {
    status: 'available',
    method: 'grad_cam',
    target_layer: 'features.-1 (last conv block)',
    mime_type: 'image/png',
    encoding: 'base64',
    data: TINY_PNG_BASE64,
    width: 96,
    height: 96,
    generation_time_ms: 12.3,
    error_code: null,
    disclaimer:
      'Grad-CAM highlights regions associated with the model output. It is not a biological explanation and must not be used as a diagnosis.',
  },
  created_at: '2026-06-20T10:00:05Z',
  disclaimer: 'This software is an educational and research portfolio project.',
}

export const MOCK_PREDICTION_READ: PredictionRead = {
  id: MOCK_PREDICTION_ID,
  module: 'histopathology',
  status: 'completed',
  request_id: 'req-1',
  client_reference: null,
  input_sha256: 'a'.repeat(64),
  input_filename_safe: 'sample-patch-96x96.png',
  input_format: 'PNG',
  input_size_bytes: 18136,
  input_width: 96,
  input_height: 96,
  processed_width: 96,
  processed_height: 96,
  model_id: 'smoke-baseline-cnn',
  model_name: 'Smoke Baseline CNN',
  model_version: '0.0.1-smoke',
  raw_probability: 0.12,
  calibrated_probability: 0.12,
  confidence_score: 0.88,
  predicted_class: 'normal',
  decision: 'negative',
  threshold: 0.5,
  review_lower_bound: 0.3,
  review_upper_bound: 0.7,
  preprocessing_time_ms: 0.8,
  inference_time_ms: 5,
  calibration_time_ms: 0.1,
  explanation_time_ms: null,
  total_time_ms: 7.1,
  explanation_requested: false,
  explanation_status: 'not_requested',
  error_code: null,
  safe_error_message: null,
  input_metadata: null,
  result: null,
  created_at: '2026-06-20T10:00:05Z',
  updated_at: '2026-06-20T10:00:05Z',
  completed_at: '2026-06-20T10:00:05Z',
}

export const handlers = [
  http.post(`${API_BASE}/api/v1/auth/login`, async ({ request }) => {
    const body = new URLSearchParams(await request.text())
    if (
      body.get('username') === VALID_CREDENTIALS.email &&
      body.get('password') === VALID_CREDENTIALS.password
    ) {
      return HttpResponse.json(tokenResponse())
    }
    return HttpResponse.json(
      { error: { code: 'AUTHENTICATION_FAILED', message: 'Could not validate credentials.' } },
      { status: 401 },
    )
  }),

  http.post(`${API_BASE}/api/v1/auth/register`, () => {
    return HttpResponse.json(MOCK_USER, { status: 201 })
  }),

  http.post(`${API_BASE}/api/v1/auth/refresh`, () => {
    return HttpResponse.json(tokenResponse())
  }),

  http.post(`${API_BASE}/api/v1/auth/logout`, () => {
    return new HttpResponse(null, { status: 204 })
  }),

  http.get(`${API_BASE}/api/v1/users/me`, ({ request }) => {
    const auth = request.headers.get('Authorization')
    if (!auth) {
      return HttpResponse.json(
        { error: { code: 'AUTHENTICATION_FAILED', message: 'Not authenticated.' } },
        { status: 401 },
      )
    }
    return HttpResponse.json(MOCK_USER)
  }),

  http.get(`${API_BASE}/api/v1/models/active`, () => {
    return HttpResponse.json(MOCK_ACTIVE_MODEL)
  }),

  http.post(`${API_BASE}/api/v1/predictions/histopathology`, () => {
    return HttpResponse.json(MOCK_PREDICTION_RESPONSE, { status: 201 })
  }),

  http.get(`${API_BASE}/api/v1/predictions/history`, () => {
    return HttpResponse.json({ items: [MOCK_PREDICTION_READ], total: 1, limit: 20, offset: 0 })
  }),

  http.get(`${API_BASE}/api/v1/predictions/:id`, ({ params }) => {
    if (params.id !== MOCK_PREDICTION_ID) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Prediction not found.' } },
        { status: 404 },
      )
    }
    return HttpResponse.json(MOCK_PREDICTION_READ)
  }),
]
