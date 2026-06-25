import { http, HttpResponse } from 'msw'

import type {
  DatasetRead,
  DatasetSampleRead,
  PredictOnSampleResponse,
} from '@/features/datasets/api'
import type { ActiveModelResponse } from '@/features/model/api'
import type { HistopathologyPredictionResponse, PredictionRead } from '@/features/predictions/api'
import type {
  ConfusionMatrixRead,
  EvaluationMetricsRead,
  EvaluationRunRead,
  EvaluationSamplePredictionRead,
} from '@/features/research/api'

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
  dataset_id: null,
  dataset_sample_id: null,
  split: null,
  ground_truth_label: null,
  is_correct: null,
  input_metadata: null,
  result: null,
  created_at: '2026-06-20T10:00:05Z',
  updated_at: '2026-06-20T10:00:05Z',
  completed_at: '2026-06-20T10:00:05Z',
}

export const MOCK_DATASET_ID = '33333333-3333-3333-3333-333333333333'
export const MOCK_SAMPLE_ID_CORRECT = '44444444-4444-4444-4444-444444444444'
export const MOCK_SAMPLE_ID_INCORRECT = '55555555-5555-5555-5555-555555555555'

export const MOCK_DATASET: DatasetRead = {
  id: MOCK_DATASET_ID,
  slug: 'synthetic-histopathology-demo',
  name: 'Synthetic Histopathology Demonstration Dataset',
  version: '1.0.0',
  description:
    'A synthetic, procedurally generated dataset used to demonstrate this research platform. It does not contain real tissue images.',
  source_name: 'Generated in-house (medrisk_ml.data.synthetic)',
  source_url: null,
  license_name: 'Project-internal, synthetic-only',
  license_url: null,
  citation: null,
  intended_use: 'Demonstrating the inference and explanation pipeline end to end.',
  prohibited_use: 'Must never be treated as medical evidence or used for diagnosis.',
  modality: 'synthetic-histopathology',
  task_type: 'binary-classification',
  classes: ['normal', 'tumor'],
  sample_count: 2,
  image_width: 96,
  image_height: 96,
  image_channels: 3,
  split_names: ['train', 'val', 'test'],
  class_distribution: { normal: 1, tumor: 1 },
  preprocessing_summary: 'Resized to 96x96, normalized per-channel.',
  known_limitations: 'Synthetic only - not representative of real tissue variability.',
  ethical_notes: 'No real patient data is involved at any stage.',
  is_synthetic: true,
  is_public: true,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

export const MOCK_DATASET_SAMPLE_CORRECT: DatasetSampleRead = {
  id: MOCK_SAMPLE_ID_CORRECT,
  dataset_id: MOCK_DATASET_ID,
  sample_key: 'train-0000',
  split: 'train',
  filename: '0000.png',
  ground_truth_label: 'normal',
  class_index: 0,
  width: 96,
  height: 96,
  mime_type: 'image/png',
  checksum_sha256: 'b'.repeat(64),
  source_reference: null,
  license_reference: null,
  is_synthetic: true,
  notes: null,
  image_url: `/api/v1/datasets/${MOCK_DATASET_ID}/samples/${MOCK_SAMPLE_ID_CORRECT}/image`,
}

export const MOCK_DATASET_SAMPLE_INCORRECT: DatasetSampleRead = {
  id: MOCK_SAMPLE_ID_INCORRECT,
  dataset_id: MOCK_DATASET_ID,
  sample_key: 'train-0001',
  split: 'train',
  filename: '0001.png',
  ground_truth_label: 'tumor',
  class_index: 1,
  width: 96,
  height: 96,
  mime_type: 'image/png',
  checksum_sha256: 'c'.repeat(64),
  source_reference: null,
  license_reference: null,
  is_synthetic: true,
  notes: null,
  image_url: `/api/v1/datasets/${MOCK_DATASET_ID}/samples/${MOCK_SAMPLE_ID_INCORRECT}/image`,
}

const MOCK_DATASET_SAMPLES = [MOCK_DATASET_SAMPLE_CORRECT, MOCK_DATASET_SAMPLE_INCORRECT]

function predictOnSampleResponse(sample: DatasetSampleRead): PredictOnSampleResponse {
  const predictedClass = 'normal'
  return {
    prediction_id: '66666666-6666-6666-6666-666666666666',
    dataset_id: MOCK_DATASET_ID,
    dataset_sample_id: sample.id,
    dataset_name: MOCK_DATASET.name,
    dataset_slug: MOCK_DATASET.slug,
    dataset_version: MOCK_DATASET.version,
    sample_key: sample.sample_key,
    split: sample.split,
    ground_truth_label: sample.ground_truth_label,
    predicted_class: predictedClass,
    is_correct: predictedClass === sample.ground_truth_label,
    decision: 'negative',
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
    warnings: ['This dataset is synthetic and demonstrative.'],
    research_disclaimer: 'This software is an educational and research portfolio project.',
  }
}

export const MOCK_PREDICT_ON_SAMPLE_RESPONSE = predictOnSampleResponse(MOCK_DATASET_SAMPLE_CORRECT)
export const MOCK_PREDICT_ON_SAMPLE_RESPONSE_INCORRECT = predictOnSampleResponse(
  MOCK_DATASET_SAMPLE_INCORRECT,
)

export const MOCK_EVALUATION_ID_COMPLETED = '77777777-7777-7777-7777-777777777777'
export const MOCK_EVALUATION_ID_PENDING = '88888888-8888-8888-8888-888888888888'

const MOCK_EVALUATION_METRICS: EvaluationMetricsRead = {
  evaluation_id: MOCK_EVALUATION_ID_COMPLETED,
  status: 'completed',
  scalar_metrics: [
    { name: 'accuracy', value: 0.5, status: 'ok', reason: null },
    {
      name: 'roc_auc',
      value: null,
      status: 'undefined',
      reason: 'Only one ground-truth class is present in this split.',
    },
  ],
  counts: { true_negative: 1, false_positive: 0, false_negative: 1, true_positive: 0 },
  confidence_intervals: null,
}

const MOCK_CONFUSION_MATRIX: ConfusionMatrixRead = {
  evaluation_id: MOCK_EVALUATION_ID_COMPLETED,
  available: true,
  class_labels: ['normal', 'tumor'],
  positive_class: 'tumor',
  matrix: [
    [1, 0],
    [1, 0],
  ],
  normalized_matrix: [
    [1, 0],
    [1, 0],
  ],
}

export const MOCK_EVALUATION_RUN_COMPLETED: EvaluationRunRead = {
  id: MOCK_EVALUATION_ID_COMPLETED,
  experiment_run_id: null,
  study_id: null,
  dataset_id: MOCK_DATASET_ID,
  model_deployment_id: null,
  model_id: 'smoke-baseline-cnn',
  model_version: '0.0.1-smoke',
  split_name: 'test',
  result_classification: 'synthetic_demo',
  status: 'completed',
  protocol_hash: 'a'.repeat(64),
  primary_metric_name: 'accuracy',
  primary_metric_value: 0.5,
  metrics: { class_names: ['normal', 'tumor'] },
  confidence_intervals: null,
  calibration_metrics: null,
  threshold_metrics: null,
  artifact_manifest: null,
  notes: 'Test fixture evaluation run.',
  created_at: '2026-06-20T10:00:05Z',
  completed_at: '2026-06-20T10:05:00Z',
  failure_reason: null,
}

export const MOCK_EVALUATION_RUN_PENDING: EvaluationRunRead = {
  id: MOCK_EVALUATION_ID_PENDING,
  experiment_run_id: null,
  study_id: null,
  dataset_id: MOCK_DATASET_ID,
  model_deployment_id: null,
  model_id: 'smoke-baseline-cnn',
  model_version: '0.0.1-smoke',
  split_name: 'test',
  result_classification: 'synthetic_demo',
  status: 'pending',
  protocol_hash: null,
  primary_metric_name: null,
  primary_metric_value: null,
  metrics: null,
  confidence_intervals: null,
  calibration_metrics: null,
  threshold_metrics: null,
  artifact_manifest: null,
  notes: null,
  created_at: '2026-06-21T10:00:00Z',
  completed_at: null,
  failure_reason: null,
}

const MOCK_EVALUATION_SAMPLE_PREDICTIONS: EvaluationSamplePredictionRead[] = [
  {
    id: '99999999-9999-9999-9999-999999999991',
    dataset_sample_id: MOCK_SAMPLE_ID_CORRECT,
    sample_key: 'train-0000',
    split: 'train',
    ground_truth_label: 'normal',
    predicted_class: 'normal',
    probabilities: { normal: 0.9, tumor: 0.1 },
    confidence: 0.9,
    is_correct: true,
    error_type: null,
    inference_duration_ms: 12.5,
  },
  {
    id: '99999999-9999-9999-9999-999999999992',
    dataset_sample_id: MOCK_SAMPLE_ID_INCORRECT,
    sample_key: 'train-0001',
    split: 'train',
    ground_truth_label: 'tumor',
    predicted_class: 'normal',
    probabilities: { normal: 0.6, tumor: 0.4 },
    confidence: 0.6,
    is_correct: false,
    error_type: 'false_negative',
    inference_duration_ms: 11.0,
  },
]

function pngBytes(): Uint8Array {
  const binary = atob(TINY_PNG_BASE64)
  return Uint8Array.from(binary, (char) => char.charCodeAt(0))
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

  http.get(`${API_BASE}/api/v1/datasets`, () => {
    return HttpResponse.json({ items: [MOCK_DATASET], total: 1, limit: 20, offset: 0 })
  }),

  http.get(`${API_BASE}/api/v1/datasets/:datasetId`, ({ params }) => {
    if (params.datasetId !== MOCK_DATASET_ID) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Dataset not found.' } },
        { status: 404 },
      )
    }
    return HttpResponse.json(MOCK_DATASET)
  }),

  http.get(`${API_BASE}/api/v1/datasets/:datasetId/samples`, ({ params, request }) => {
    if (params.datasetId !== MOCK_DATASET_ID) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Dataset not found.' } },
        { status: 404 },
      )
    }
    const url = new URL(request.url)
    const split = url.searchParams.get('split')
    const classIndex = url.searchParams.get('class_index')
    const items = MOCK_DATASET_SAMPLES.filter(
      (sample) =>
        (!split || sample.split === split) &&
        (classIndex === null || sample.class_index === Number(classIndex)),
    )
    return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0 })
  }),

  http.get(`${API_BASE}/api/v1/datasets/:datasetId/samples/:sampleId`, ({ params }) => {
    const sample = MOCK_DATASET_SAMPLES.find((item) => item.id === params.sampleId)
    if (params.datasetId !== MOCK_DATASET_ID || !sample) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Dataset sample not found.' } },
        { status: 404 },
      )
    }
    return HttpResponse.json(sample)
  }),

  http.get(`${API_BASE}/api/v1/datasets/:datasetId/samples/:sampleId/image`, ({ params }) => {
    const sample = MOCK_DATASET_SAMPLES.find((item) => item.id === params.sampleId)
    if (params.datasetId !== MOCK_DATASET_ID || !sample) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Dataset sample not found.' } },
        { status: 404 },
      )
    }
    return new HttpResponse(pngBytes(), { headers: { 'Content-Type': 'image/png' } })
  }),

  http.post(`${API_BASE}/api/v1/datasets/:datasetId/samples/:sampleId/predict`, ({ params }) => {
    const sample = MOCK_DATASET_SAMPLES.find((item) => item.id === params.sampleId)
    if (params.datasetId !== MOCK_DATASET_ID || !sample) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Dataset sample not found.' } },
        { status: 404 },
      )
    }
    return HttpResponse.json(predictOnSampleResponse(sample), { status: 201 })
  }),

  http.get(`${API_BASE}/api/v1/research/evaluations`, ({ request }) => {
    const url = new URL(request.url)
    const datasetId = url.searchParams.get('dataset_id')
    const status = url.searchParams.get('status')
    const items = [MOCK_EVALUATION_RUN_COMPLETED, MOCK_EVALUATION_RUN_PENDING].filter(
      (run) => (!datasetId || run.dataset_id === datasetId) && (!status || run.status === status),
    )
    return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0 })
  }),

  http.get(`${API_BASE}/api/v1/research/evaluations/:evaluationId`, ({ params }) => {
    const run = [MOCK_EVALUATION_RUN_COMPLETED, MOCK_EVALUATION_RUN_PENDING].find(
      (item) => item.id === params.evaluationId,
    )
    if (!run) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Evaluation run not found.' } },
        { status: 404 },
      )
    }
    return HttpResponse.json(run)
  }),

  http.get(`${API_BASE}/api/v1/research/evaluations/:evaluationId/metrics`, ({ params }) => {
    if (params.evaluationId !== MOCK_EVALUATION_ID_COMPLETED) {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Evaluation run not found.' } },
        { status: 404 },
      )
    }
    return HttpResponse.json(MOCK_EVALUATION_METRICS)
  }),

  http.get(
    `${API_BASE}/api/v1/research/evaluations/:evaluationId/confusion-matrix`,
    ({ params }) => {
      if (params.evaluationId !== MOCK_EVALUATION_ID_COMPLETED) {
        return HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'Evaluation run not found.' } },
          { status: 404 },
        )
      }
      return HttpResponse.json(MOCK_CONFUSION_MATRIX)
    },
  ),

  http.get(
    `${API_BASE}/api/v1/research/evaluations/:evaluationId/errors`,
    ({ params, request }) => {
      if (params.evaluationId !== MOCK_EVALUATION_ID_COMPLETED) {
        return HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'Evaluation run not found.' } },
          { status: 404 },
        )
      }
      const url = new URL(request.url)
      const isCorrect = url.searchParams.get('is_correct')
      const items = MOCK_EVALUATION_SAMPLE_PREDICTIONS.filter(
        (item) => isCorrect === null || String(item.is_correct) === isCorrect,
      )
      return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0 })
    },
  ),
]
