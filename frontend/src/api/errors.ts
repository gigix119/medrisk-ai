/** Mirrors app/schemas/common.py:ErrorDetail/ErrorResponse on the backend. */
export interface ApiErrorDetail {
  code: string
  message: string
  details?: Record<string, unknown> | null
  request_id?: string | null
}

/** Backend error codes that get a friendlier, localized message in the UI. Unknown codes
 * fall back to the backend's own message, which is itself written to be user-safe. */
const FRIENDLY_MESSAGES: Record<string, string> = {
  AUTHENTICATION_FAILED: 'Incorrect email or password.',
  TOKEN_EXPIRED: 'Your session has expired. Please log in again.',
  TOKEN_REVOKED: 'Your session is no longer valid. Please log in again.',
  CONFLICT: 'An account with this email already exists.',
  UPLOAD_TOO_LARGE: 'The selected file is too large.',
  UPLOAD_EMPTY: 'The selected file is empty. Choose a different image.',
  UNSUPPORTED_IMAGE_FORMAT: 'Only PNG and JPEG images are supported.',
  IMAGE_MULTIFRAME_NOT_SUPPORTED: 'Animated images are not supported. Use a single still frame.',
  IMAGE_MIME_MISMATCH:
    'The file content does not match its declared type. Try re-saving the image and uploading it again.',
  IMAGE_DIMENSIONS_INVALID: 'The image dimensions do not match the model requirements.',
  MODEL_NOT_READY: 'The analysis model is temporarily unavailable.',
  MODEL_NOT_CONFIGURED: 'No analysis model is currently configured.',
  INFERENCE_QUEUE_FULL: 'The analysis service is busy. Please try again shortly.',
  INFERENCE_TIMEOUT: 'The analysis took too long to complete. Please try again.',
  INFERENCE_FAILED: 'The analysis could not be completed. Please try again.',
  SERVICE_UNAVAILABLE: 'The analysis service is temporarily unavailable. Please try again shortly.',
  NOT_FOUND: 'We could not find this analysis. It may not exist or you may not have access to it.',
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: Record<string, unknown> | null
  readonly requestId: string | null

  constructor(status: number, detail: ApiErrorDetail) {
    super(FRIENDLY_MESSAGES[detail.code] ?? detail.message)
    this.name = 'ApiError'
    this.code = detail.code
    this.status = status
    this.details = detail.details ?? null
    this.requestId = detail.request_id ?? null
  }
}

export class NetworkError extends Error {
  constructor(cause?: unknown) {
    super('Could not reach the server. Check your connection and try again.')
    this.name = 'NetworkError'
    this.cause = cause
  }
}
