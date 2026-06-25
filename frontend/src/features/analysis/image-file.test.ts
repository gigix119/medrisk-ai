import { afterEach, describe, expect, it, vi } from 'vitest'

import { MAX_UPLOAD_BYTES } from './constants'
import { validateImageFile } from './image-file'

const REQUIRED = { width: 96, height: 96 }

function mockDecodableBitmap(width: number, height: number) {
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => ({ width, height, close: vi.fn() })),
  )
}

function mockUndecodable() {
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => {
      throw new Error('cannot decode')
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('validateImageFile', () => {
  it('accepts a file matching the required dimensions', async () => {
    mockDecodableBitmap(96, 96)
    const file = new File(['x'], 'patch.png', { type: 'image/png' })

    expect(await validateImageFile(file, REQUIRED)).toEqual({ ok: true, width: 96, height: 96 })
  })

  it('rejects an empty file', async () => {
    const file = new File([], 'empty.png', { type: 'image/png' })

    expect(await validateImageFile(file, REQUIRED)).toEqual({ ok: false, error: { code: 'EMPTY' } })
  })

  it('rejects an unsupported mime type', async () => {
    const file = new File(['x'], 'patch.gif', { type: 'image/gif' })

    expect(await validateImageFile(file, REQUIRED)).toEqual({
      ok: false,
      error: { code: 'UNSUPPORTED_TYPE' },
    })
  })

  it('rejects a file larger than the max upload size', async () => {
    const file = new File([new Uint8Array(MAX_UPLOAD_BYTES + 1)], 'big.png', {
      type: 'image/png',
    })

    expect(await validateImageFile(file, REQUIRED)).toEqual({
      ok: false,
      error: { code: 'TOO_LARGE' },
    })
  })

  it('rejects a file that cannot be decoded as an image', async () => {
    mockUndecodable()
    const file = new File(['x'], 'patch.png', { type: 'image/png' })

    expect(await validateImageFile(file, REQUIRED)).toEqual({
      ok: false,
      error: { code: 'CORRUPT' },
    })
  })

  it('rejects a decodable image whose dimensions do not match the model input contract', async () => {
    mockDecodableBitmap(50, 50)
    const file = new File(['x'], 'patch.png', { type: 'image/png' })

    expect(await validateImageFile(file, REQUIRED)).toEqual({
      ok: false,
      error: {
        code: 'DIMENSIONS_MISMATCH',
        expected: { width: 96, height: 96 },
        actual: { width: 50, height: 50 },
      },
    })
  })

  it('skips the dimension check when no required dimensions are given', async () => {
    mockDecodableBitmap(50, 50)
    const file = new File(['x'], 'patch.png', { type: 'image/png' })

    expect(await validateImageFile(file, null)).toEqual({ ok: true, width: 50, height: 50 })
  })
})
