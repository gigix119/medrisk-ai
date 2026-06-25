/** Mirrors app/core/config.py's MAX_UPLOAD_BYTES - keep these two in sync. The backend
 * enforces this for real while streaming the upload; this is only a fast client-side check. */
export const MAX_UPLOAD_BYTES = 5_242_880

export const SUPPORTED_MIME_TYPES = ['image/png', 'image/jpeg'] as const

export const SUPPORTED_EXTENSIONS = ['.png', '.jpg', '.jpeg'] as const
