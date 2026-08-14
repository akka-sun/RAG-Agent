import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  conversationsApi,
  documentsApi,
  healthApi,
  knowledgeBasesApi,
} from './resources'

afterEach(() => {
  vi.unstubAllGlobals()
})

function respondJson(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

describe('resource APIs', () => {
  it('uses encoded knowledge-base and document endpoint URLs', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(respondJson([])))
    vi.stubGlobal('fetch', fetchMock)

    await documentsApi.get('kb / one', 'doc / two')
    await documentsApi.image('kb / one', 'doc / two', 3)
    await documentsApi.task('task / three')

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/v1/knowledge-bases/kb%20%2F%20one/documents/doc%20%2F%20two',
      '/api/v1/knowledge-bases/kb%20%2F%20one/documents/doc%20%2F%20two/images/3',
      '/api/v1/ingestion-tasks/task%20%2F%20three',
    ])
  })

  it('uploads multipart files without manually setting content type', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respondJson({
      document_id: 'document-id', task_id: 'task-id', status: 'pending',
    }, 202))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['content'], 'notes.txt', { type: 'text/plain' })

    await documentsApi.upload('knowledge-base', file, 'text')

    const [, request] = fetchMock.mock.calls[0]
    expect(request.body).toBeInstanceOf(FormData)
    expect(request.headers).toBeUndefined()
    expect(request.body.get('file')).toBe(file)
    expect(request.body.get('parser')).toBe('text')
  })

  it('exposes knowledge-base, conversation, and health routes', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(respondJson({ status: 'ok' })))
    vi.stubGlobal('fetch', fetchMock)

    await knowledgeBasesApi.list()
    await knowledgeBasesApi.create({
      name: 'Docs', description: '', embedding_model: 'model', embedding_dimension: 1024,
    })
    await conversationsApi.list('kb')
    await conversationsApi.create('kb', { title: 'New chat' })
    await conversationsApi.get('conversation')
    await conversationsApi.messages('conversation')
    await healthApi.live()

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/v1/knowledge-bases',
      '/api/v1/knowledge-bases',
      '/api/v1/knowledge-bases/kb/conversations',
      '/api/v1/knowledge-bases/kb/conversations',
      '/api/v1/conversations/conversation',
      '/api/v1/conversations/conversation/messages',
      '/api/v1/health/live',
    ])
  })
})
