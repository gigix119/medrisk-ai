import { MAX_UPLOAD_BYTES, SUPPORTED_MIME_TYPES } from './constants'

export interface RequiredDimensions {
  width: number
  height: number
}

export type ImageValidationError =
  | { code: 'EMPTY' }
  | { code: 'UNSUPPORTED_TYPE' }
  | { code: 'TOO_LARGE' }
  | { code: 'CORRUPT' }
  | { code: 'DIMENSIONS_MISMATCH'; expected: RequiredDimensions; actual: RequiredDimensions }

export type ImageValidationResult =
  | { ok: true; width: number; height: number }
  | { ok: false; error: ImageValidationError }

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

/** Decodes the file to confirm it is a real, readable image and to read its pixel
 * dimensions. Rejects (caught by the caller) on corrupt/undecodable data. */
async function readImageDimensions(file: File): Promise<RequiredDimensions> {
  const bitmap = await createImageBitmap(file)
  try {
    return { width: bitmap.width, height: bitmap.height }
  } finally {
    bitmap.close()
  }
}

/** Client-side validation only - a fast, friendly first pass. The backend re-validates
 * every one of these constraints independently and is the actual source of truth. */
export async function validateImageFile(
  file: File,
  requiredDimensions: RequiredDimensions | null,
): Promise<ImageValidationResult> {
  if (file.size === 0) return { ok: false, error: { code: 'EMPTY' } }
  if (file.size > MAX_UPLOAD_BYTES) return { ok: false, error: { code: 'TOO_LARGE' } }
  if (!SUPPORTED_MIME_TYPES.includes(file.type as (typeof SUPPORTED_MIME_TYPES)[number])) {
    return { ok: false, error: { code: 'UNSUPPORTED_TYPE' } }
  }

  let actual: RequiredDimensions
  try {
    actual = await readImageDimensions(file)
  } catch {
    return { ok: false, error: { code: 'CORRUPT' } }
  }

  if (
    requiredDimensions &&
    (actual.width !== requiredDimensions.width || actual.height !== requiredDimensions.height)
  ) {
    return {
      ok: false,
      error: { code: 'DIMENSIONS_MISMATCH', expected: requiredDimensions, actual },
    }
  }

  return { ok: true, width: actual.width, height: actual.height }
}
