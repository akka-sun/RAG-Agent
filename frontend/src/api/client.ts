import type { ErrorResponse } from '@/types/api'

export interface ApiRequestInit extends Omit<RequestInit, 'body'> {
  body?: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export interface BlobResponse {
  blob: Blob
  contentType: string | null
  contentDisposition: string | null
  filename: string | null
  status: number
}

export async function apiJson<T>(path: string, init: ApiRequestInit = {}): Promise<T | undefined> {
  const response = await fetch(path, createRequest(init))
  await throwForError(response)
  if (response.status === 204) return undefined
  return response.json() as Promise<T>
}

export async function apiBlob(path: string, init: ApiRequestInit = {}): Promise<BlobResponse> {
  const response = await fetch(path, createRequest(init))
  await throwForError(response)
  const contentDisposition = response.headers.get('content-disposition')
  return {
    blob: await response.blob(),
    contentType: response.headers.get('content-type'),
    contentDisposition,
    filename: parseFilename(contentDisposition),
    status: response.status,
  }
}

function createRequest(init: ApiRequestInit): RequestInit {
  const { body, headers: providedHeaders, ...request } = init
  const headers = toHeaderRecord(providedHeaders)
  if (isJsonBody(body)) {
    if (!hasHeader(headers, 'content-type')) headers['Content-Type'] = 'application/json'
    return { ...request, body: JSON.stringify(body), headers }
  }
  return {
    ...request,
    ...(body === undefined ? {} : { body: body as BodyInit }),
    ...(Object.keys(headers).length === 0 ? {} : { headers }),
  }
}

function isJsonBody(body: unknown): body is object | null {
  return body === null || (typeof body === 'object'
    && !(body instanceof FormData)
    && !(body instanceof Blob)
    && !(body instanceof URLSearchParams)
    && !(body instanceof ArrayBuffer)
    && !ArrayBuffer.isView(body)
    && !(body instanceof ReadableStream))
}

function toHeaderRecord(headers?: HeadersInit): Record<string, string> {
  if (!headers) return {}
  if (headers instanceof Headers || Array.isArray(headers)) return Object.fromEntries(new Headers(headers))
  return { ...headers }
}

function hasHeader(headers: Record<string, string>, name: string): boolean {
  return Object.keys(headers).some((header) => header.toLowerCase() === name)
}

async function throwForError(response: Response): Promise<void> {
  if (response.ok) return
  const error = await readError(response)
  throw new ApiError(response.status, error.code, error.message, error.details)
}

async function readError(response: Response): Promise<{ code: string, message: string, details?: unknown }> {
  if (response.headers.get('content-type')?.includes('application/json')) {
    try {
      const payload: unknown = await response.json()
      if (isErrorResponse(payload)) return payload.error
    } catch {
      // Use the generic error when an error body is malformed.
    }
  }
  return { code: 'http_error', message: `Request failed with status ${response.status}` }
}

function isErrorResponse(payload: unknown): payload is ErrorResponse {
  if (typeof payload !== 'object' || payload === null || !('error' in payload)) return false
  const { error } = payload
  return typeof error === 'object' && error !== null
    && 'code' in error && typeof error.code === 'string'
    && 'message' in error && typeof error.message === 'string'
}

function parseFilename(contentDisposition: string | null): string | null {
  if (!contentDisposition) return null
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition)?.[1]
  if (encoded) {
    try { return decodeURIComponent(encoded) } catch { return null }
  }
  return /filename="?([^";]+)"?/i.exec(contentDisposition)?.[1] ?? null
}
