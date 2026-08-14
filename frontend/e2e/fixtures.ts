import { expect, test as base, type Page, type Route } from '@playwright/test'
import type {
  Conversation,
  DocumentRecord,
  IngestionTask,
  KnowledgeBase,
  KnowledgeBaseCreate,
  Message,
  MessageCitation,
  ReadinessResponse,
} from '../src/types/api'

export const KB_ID = '11111111-1111-4111-8111-111111111111'
export const DOCUMENT_ID = '22222222-2222-4222-8222-222222222222'
export const TASK_ID = '33333333-3333-4333-8333-333333333333'
export const CONVERSATION_ID = '44444444-4444-4444-8444-444444444444'
export const CHUNK_ID = 'chunk-warranty-001'
export const FIXED_TIME = '2026-08-14T08:00:00.000Z'
export const ANSWER = '产品保修期为两年 [S1]。'

const citation: MessageCitation = {
  id: '55555555-5555-4555-8555-555555555555',
  document_id: DOCUMENT_ID,
  chunk_id: CHUNK_ID,
  source_label: 'S1',
  quote: '产品保修期为两年',
  page_number: 1,
  section: '保修政策',
  score: 0.98,
  metadata: { filename: 'sample.md' },
}

interface MockApiState {
  frontendOrigin: string
  knowledgeBases: KnowledgeBase[]
  knowledgeBaseCreatePayloads: KnowledgeBaseCreate[]
  documents: DocumentRecord[]
  tasks: Map<string, IngestionTask>
  taskPollCounts: Map<string, number>
  conversations: Conversation[]
  messagesByConversation: Map<string, Message[]>
  failNextStreams: number
  streamAttempts: number
  lifecycle: string[]
  originViolations: string[]
  unknownRequests: string[]
}

export interface MockApi {
  state: MockApiState
  seedCompleteWorkflow(): void
  failNextStream(count?: number): void
  acknowledgeOriginViolations(): void
}

type Fixtures = { mockApi: MockApi }

function knowledgeBase(input: Partial<KnowledgeBase> = {}): KnowledgeBase {
  return {
    id: KB_ID,
    name: '产品资料库',
    description: '',
    embedding_model: 'text-embedding-3-small',
    embedding_dimension: 1536,
    created_at: FIXED_TIME,
    updated_at: FIXED_TIME,
    ...input,
  }
}

function readiness(): ReadinessResponse {
  return {
    status: 'healthy',
    services: {
      postgresql: { status: 'healthy', latency_ms: 3, error: null },
      redis: { status: 'healthy', latency_ms: 1, error: null },
      minio: { status: 'healthy', latency_ms: 5, error: null },
      milvus: { status: 'healthy', latency_ms: 8, error: null },
    },
  }
}

function documentRecord(input: Partial<DocumentRecord> = {}): DocumentRecord {
  return {
    id: DOCUMENT_ID,
    knowledge_base_id: KB_ID,
    filename: 'sample.md',
    content_type: 'text/markdown',
    size_bytes: 43,
    parser_name: 'local',
    source_object_key: `${KB_ID}/${DOCUMENT_ID}/source/sample.md`,
    parsed_object_key: null,
    status: 'pending',
    chunk_count: 0,
    error: null,
    created_at: FIXED_TIME,
    updated_at: FIXED_TIME,
    ...input,
  }
}

function conversation(input: Partial<Conversation> = {}): Conversation {
  return {
    id: CONVERSATION_ID,
    knowledge_base_id: KB_ID,
    title: '保修政策咨询',
    created_at: FIXED_TIME,
    updated_at: FIXED_TIME,
    ...input,
  }
}

function ingestionTask(status: IngestionTask['status'], pollCount: number): IngestionTask {
  const stages = { pending: 'queued', processing: 'chunking', completed: 'completed', failed: 'failed' }
  const progress = { pending: 10, processing: 60, completed: 100, failed: 60 }
  return {
    id: TASK_ID,
    document_id: DOCUMENT_ID,
    arq_job_id: 'mock-arq-job',
    status,
    stage: stages[status],
    progress: progress[status],
    error: status === 'failed' ? '模拟摄取失败' : null,
    created_at: FIXED_TIME,
    started_at: pollCount > 1 ? FIXED_TIME : null,
    completed_at: status === 'completed' ? FIXED_TIME : null,
  }
}

function messages(content: string): Message[] {
  return [
    {
      id: '66666666-6666-4666-8666-666666666666',
      conversation_id: CONVERSATION_ID,
      role: 'user',
      content,
      status: 'completed',
      created_at: FIXED_TIME,
      token_count: 12,
      citations: [],
    },
    {
      id: '77777777-7777-4777-8777-777777777777',
      conversation_id: CONVERSATION_ID,
      role: 'assistant',
      content: ANSWER,
      status: 'completed',
      created_at: '2026-08-14T08:00:01.000Z',
      token_count: 18,
      citations: [citation],
    },
  ]
}

function json(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({ status, contentType: 'application/json; charset=utf-8', body: JSON.stringify(body) })
}

function noContent(route: Route): Promise<void> {
  return route.fulfill({ status: 204, body: '' })
}

function sseEvent(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

async function installApiRoutes(page: Page, state: MockApiState): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const method = request.method()
    const url = new URL(request.url())
    if (url.origin !== state.frontendOrigin) {
      state.originViolations.push(`${method} ${url.href}`)
      await route.abort('blockedbyclient')
      return
    }
    const path = decodeURIComponent(url.pathname)
    const segments = path.split('/').filter(Boolean)

    if (method === 'GET' && path === '/api/v1/health/live') {
      await json(route, { status: 'ok' })
      return
    }

    if (method === 'GET' && path === '/api/v1/health/ready') {
      await json(route, readiness())
      return
    }

    if (path === '/api/v1/knowledge-bases' && method === 'GET') {
      await json(route, state.knowledgeBases)
      return
    }

    if (path === '/api/v1/knowledge-bases' && method === 'POST') {
      const input = request.postDataJSON() as KnowledgeBaseCreate
      state.knowledgeBaseCreatePayloads.push(input)
      const item = knowledgeBase(input)
      state.knowledgeBases.push(item)
      await json(route, item, 201)
      return
    }

    if (segments.length === 4 && segments[2] === 'knowledge-bases') {
      const knowledgeBaseId = segments[3]
      const item = state.knowledgeBases.find((entry) => entry.id === knowledgeBaseId)
      if (method === 'GET' && item) {
        await json(route, item)
        return
      }
      if (method === 'DELETE' && item) {
        state.knowledgeBases = state.knowledgeBases.filter((entry) => entry.id !== knowledgeBaseId)
        state.documents = state.documents.filter((entry) => entry.knowledge_base_id !== knowledgeBaseId)
        state.conversations = state.conversations.filter((entry) => entry.knowledge_base_id !== knowledgeBaseId)
        await noContent(route)
        return
      }
    }

    if (segments.length === 5 && segments[2] === 'knowledge-bases' && segments[4] === 'documents') {
      const knowledgeBaseId = segments[3]
      if (method === 'GET') {
        await json(route, state.documents.filter((entry) => entry.knowledge_base_id === knowledgeBaseId))
        return
      }
      if (method === 'POST') {
        const item = documentRecord({ knowledge_base_id: knowledgeBaseId })
        state.documents.push(item)
        state.tasks.set(TASK_ID, ingestionTask('pending', 0))
        state.taskPollCounts.set(TASK_ID, 0)
        await json(route, { document_id: DOCUMENT_ID, task_id: TASK_ID, status: 'pending' }, 202)
        return
      }
    }

    if (segments.length === 6 && segments[2] === 'knowledge-bases' && segments[4] === 'documents') {
      const documentId = segments[5]
      const item = state.documents.find((entry) => entry.id === documentId)
      if (method === 'GET' && item) {
        await json(route, item)
        return
      }
      if (method === 'DELETE' && item) {
        state.documents = state.documents.filter((entry) => entry.id !== documentId)
        await noContent(route)
        return
      }
    }

    if (segments.length === 7 && segments[2] === 'knowledge-bases' && segments[4] === 'documents' && segments[6] === 'retry' && method === 'POST') {
      const nextTask = ingestionTask('pending', 0)
      state.tasks.set(TASK_ID, nextTask)
      state.taskPollCounts.set(TASK_ID, 0)
      await json(route, nextTask, 202)
      return
    }

    if (segments.length === 4 && segments[2] === 'ingestion-tasks' && method === 'GET') {
      const taskId = segments[3]
      const pollCount = (state.taskPollCounts.get(taskId) ?? 0) + 1
      state.taskPollCounts.set(taskId, pollCount)
      const status = pollCount === 1 ? 'pending' : pollCount === 2 ? 'processing' : 'completed'
      const task = ingestionTask(status, pollCount)
      state.tasks.set(taskId, task)
      if (status === 'completed') {
        state.documents = state.documents.map((entry) => entry.id === DOCUMENT_ID
          ? documentRecord({ status: 'completed', chunk_count: 1, parsed_object_key: `${KB_ID}/${DOCUMENT_ID}/parsed.md` })
          : entry)
      }
      await json(route, task)
      return
    }

    if (segments.length === 5 && segments[2] === 'knowledge-bases' && segments[4] === 'conversations') {
      const knowledgeBaseId = segments[3]
      if (method === 'GET') {
        await json(route, state.conversations.filter((entry) => entry.knowledge_base_id === knowledgeBaseId))
        return
      }
      if (method === 'POST') {
        const input = request.postDataJSON() as { title: string }
        const item = conversation({ knowledge_base_id: knowledgeBaseId, title: input.title })
        state.conversations.push(item)
        state.messagesByConversation.set(item.id, [])
        await json(route, item, 201)
        return
      }
    }

    if (segments.length === 4 && segments[2] === 'conversations') {
      const conversationId = segments[3]
      const item = state.conversations.find((entry) => entry.id === conversationId)
      if (method === 'GET' && item) {
        await json(route, item)
        return
      }
      if (method === 'DELETE' && item) {
        state.conversations = state.conversations.filter((entry) => entry.id !== conversationId)
        state.messagesByConversation.delete(conversationId)
        await noContent(route)
        return
      }
    }

    if (segments.length === 5 && segments[2] === 'conversations' && segments[4] === 'messages' && method === 'GET') {
      const persisted = state.messagesByConversation.get(segments[3]) ?? []
      state.lifecycle.push(`messages:get:${persisted.length ? 'visible' : 'empty'}`)
      await json(route, persisted)
      return
    }

    if (segments.length === 6 && segments[2] === 'conversations' && segments[4] === 'messages' && segments[5] === 'stream' && method === 'POST') {
      const conversationId = segments[3]
      const input = request.postDataJSON() as { content: string }
      state.streamAttempts += 1
      const attempt = state.streamAttempts
      state.lifecycle.push(`stream:${attempt}:start`)
      if (state.failNextStreams > 0) {
        state.failNextStreams -= 1
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream; charset=utf-8',
          headers: { 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no' },
          body: [
            sseEvent('message_start', { conversation_id: conversationId }),
            sseEvent('agent_status', { status: '正在分析问题' }),
            sseEvent('error', { message: '模拟流式失败' }),
          ].join(''),
        })
        state.lifecycle.push(`stream:${attempt}:error-fulfilled`)
        return
      }

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream; charset=utf-8',
        headers: { 'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no' },
        body: [
          sseEvent('message_start', { conversation_id: conversationId }),
          sseEvent('agent_status', { status: '正在分析问题' }),
          sseEvent('token', { text: '产品保修期' }),
          sseEvent('token', { text: '为两年' }),
          sseEvent('token', { text: '[S1]。' }),
          sseEvent('citation', {
            source_label: 'S1', document_id: DOCUMENT_ID, chunk_id: CHUNK_ID,
            quote: '产品保修期为两年', page_number: 1, section: '保修政策', score: 0.98,
          }),
          sseEvent('message_end', { content: ANSWER }),
        ].join(''),
      })
      state.lifecycle.push(`stream:${attempt}:terminal-fulfilled`)
      state.messagesByConversation.set(conversationId, messages(input.content))
      state.lifecycle.push(`stream:${attempt}:persisted-visible`)
      return
    }

    state.unknownRequests.push(`${method} ${path}`)
    await json(route, { error: { code: 'unhandled_mock_route', message: `${method} ${path}`, details: null } }, 501)
  })
}

export const test = base.extend<Fixtures>({
  mockApi: async ({ page, baseURL }, use) => {
    const state: MockApiState = {
      frontendOrigin: new URL(baseURL ?? 'http://127.0.0.1:4173').origin,
      knowledgeBases: [],
      knowledgeBaseCreatePayloads: [],
      documents: [],
      tasks: new Map(),
      taskPollCounts: new Map(),
      conversations: [],
      messagesByConversation: new Map(),
      failNextStreams: 0,
      streamAttempts: 0,
      lifecycle: [],
      originViolations: [],
      unknownRequests: [],
    }
    const api: MockApi = {
      state,
      seedCompleteWorkflow() {
        state.knowledgeBases = [knowledgeBase()]
        state.documents = [documentRecord({ status: 'completed', chunk_count: 1, parsed_object_key: `${KB_ID}/${DOCUMENT_ID}/parsed.md` })]
        state.conversations = [conversation()]
        state.messagesByConversation.set(CONVERSATION_ID, [])
      },
      failNextStream(count = 1) {
        state.failNextStreams = count
      },
      acknowledgeOriginViolations() {
        state.originViolations = []
      },
    }
    await installApiRoutes(page, state)
    await use(api)
    expect(state.originViolations, `检测到跨源 API 请求：${state.originViolations.join(', ')}`).toEqual([])
    expect(state.unknownRequests, `fixture 未处理 API 请求：${state.unknownRequests.join(', ')}`).toEqual([])
  },
})

export { expect }
