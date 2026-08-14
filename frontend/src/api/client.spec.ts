import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiBlob, apiJson } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiJson', () => {
  it('normalizes structured backend errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ error: { code: 'document_too_large', message: 'too large' } }),
      { status: 413, headers: { 'content-type': 'application/json' } },
    )))

    await expect(apiJson('/documents')).rejects.toMatchObject({
      status: 413, code: 'document_too_large', message: 'too large',
    })
  })

  it('normalizes non-JSON gateway errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad Gateway', { status: 502 })))

    await expect(apiJson('/documents')).rejects.toMatchObject({
      status: 502,
      code: 'http_error',
      message: 'Request failed with status 502',
    })
  })

  it('returns undefined for a successful 204 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))

    await expect(apiJson('/documents', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('serializes JSON bodies and sets a JSON content type', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'kb-1' }), {
      headers: { 'content-type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await apiJson('/knowledge-bases', { method: 'POST', body: { name: 'Docs' } })

    expect(fetchMock).toHaveBeenCalledWith('/knowledge-bases', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ name: 'Docs' }),
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }))
  })
})

describe('apiBlob', () => {
  it('returns the blob and download metadata', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('file content', {
      headers: {
        'content-type': 'text/plain',
        'content-disposition': "attachment; filename*=UTF-8''notes.txt",
      },
    })))

    const result = await apiBlob('/download')

    expect(result.blob.size).toBe(12)
    expect(result).toMatchObject({
      contentType: 'text/plain',
      contentDisposition: "attachment; filename*=UTF-8''notes.txt",
      filename: 'notes.txt',
      status: 200,
    })
  })

  it('throws ApiError for a failed binary request', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Unavailable', { status: 503 })))

    await expect(apiBlob('/download')).rejects.toBeInstanceOf(ApiError)
  })
})
