import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { SseEvent } from '@/api/sse'
import { useChatStore } from './chat'
import { useConversationStore } from './conversations'

const streamMock = vi.hoisted(() => vi.fn())
const conversationsApi = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), get: vi.fn(), delete: vi.fn(), messages: vi.fn(),
}))

vi.mock('@/api/sse', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/sse')>(),
  streamConversationMessage: streamMock,
}))
vi.mock('@/api/resources', () => ({ conversationsApi }))

class ControlledEvents implements AsyncIterable<SseEvent>, AsyncIterator<SseEvent> {
  private queued: IteratorResult<SseEvent>[] = []
  private waiting: ((result: IteratorResult<SseEvent>) => void) | undefined

  [Symbol.asyncIterator](): AsyncIterator<SseEvent> { return this }

  next(): Promise<IteratorResult<SseEvent>> {
    const queued = this.queued.shift()
    if (queued) return Promise.resolve(queued)
    return new Promise((resolve) => { this.waiting = resolve })
  }

  push(event: SseEvent): void { this.deliver({ value: event, done: false }) }
  end(): void { this.deliver({ value: undefined, done: true }) }

  private deliver(result: IteratorResult<SseEvent>): void {
    if (this.waiting) {
      const resolve = this.waiting
      this.waiting = undefined
      resolve(result)
    } else {
      this.queued.push(result)
    }
  }
}

function events(...items: SseEvent[]): AsyncIterable<SseEvent> {
  return (async function* () { yield* items })()
}

const conversationId = '11111111-1111-4111-8111-111111111111'
const secondConversationId = '22222222-2222-4222-8222-222222222222'
const persistedMessages = [
  { id: 'u1', conversation_id: conversationId, role: 'user', content: 'hello world', status: 'completed', created_at: '2026-08-14T00:00:00Z', token_count: null, citations: [] },
  { id: 'a1', conversation_id: conversationId, role: 'assistant', content: 'final answer', status: 'completed', created_at: '2026-08-14T00:00:01Z', token_count: null, citations: [] },
]

describe('chat store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    conversationsApi.messages.mockResolvedValue(persistedMessages)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fails a current stream when a successful SSE response has a null body and allows explicit retry', async () => {
    const actualSse = await vi.importActual<typeof import('@/api/sse')>('@/api/sse')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 200 })))
    streamMock.mockImplementation(actualSse.streamConversationMessage)
    const store = useChatStore()

    await store.send(conversationId, 'question')

    expect(store.phase).toBe('failed')
    expect(store.error).toBe('连接提前结束，请重试。')
    expect(store.draftAssistant).toBe('')
    streamMock.mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'message_end', data: { content: 'retried' } },
    ))
    await expect(store.retry(conversationId)).resolves.toBeUndefined()
    expect(store.draftAssistant).toBe('retried')
  })

  it('fails on clean EOF before a terminal event while preserving partial output for explicit retry', async () => {
    streamMock.mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'token', data: { text: 'partial' } },
    )).mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'message_end', data: { content: 'recovered' } },
    ))
    const store = useChatStore()

    await store.send(conversationId, 'question')

    expect(store.phase).toBe('failed')
    expect(store.error).toBe('连接提前结束，请重试。')
    expect(store.draftAssistant).toBe('partial')
    await expect(store.retry(conversationId)).resolves.toBeUndefined()
    expect(store.draftAssistant).toBe('recovered')
  })

  it('rejects blank input and overlapping sends while keeping one optimistic user message outside persisted messages', async () => {
    const controlled = new ControlledEvents()
    streamMock.mockReturnValue(controlled)
    const conversations = useConversationStore()
    conversations.messagesByConversation[conversationId] = []
    const store = useChatStore()

    await expect(store.send(conversationId, '   ')).rejects.toThrow('消息不能为空')
    const pending = store.send(conversationId, '  hello world  ')
    await vi.waitFor(() => expect(streamMock).toHaveBeenCalledTimes(1))

    expect(store.optimisticUser).toEqual({ conversationId, content: 'hello world' })
    expect(conversations.messagesByConversation[conversationId]).toEqual([])
    await expect(store.send(conversationId, 'second')).rejects.toThrow('消息正在生成中')
    expect(streamMock).toHaveBeenCalledTimes(1)

    store.cancel()
    controlled.end()
    await pending
    expect(store.phase).toBe('cancelled')
  })

  it('reduces every event, reconstructs token spacing, deduplicates citations, and refreshes authoritative messages', async () => {
    const controlled = new ControlledEvents()
    streamMock.mockReturnValue(controlled)
    const store = useChatStore()
    const conversations = useConversationStore()
    const pending = store.send(conversationId, 'question')

    controlled.push({ event: 'message_start', data: { conversation_id: conversationId } })
    await vi.waitFor(() => expect(store.phase).toBe('streaming'))
    controlled.push({ event: 'agent_status', data: { status: 'thinking' } })
    await vi.waitFor(() => expect(store.status).toBe('thinking'))
    controlled.push({ event: 'retrieval_start', data: { query: 'question' } })
    await vi.waitFor(() => expect(store.retrievalDetails).toEqual({ query: 'question' }))
    expect(store.phase).toBe('retrieving')
    controlled.push({ event: 'retrieval_result', data: { count: 1 } })
    await vi.waitFor(() => expect(store.retrievalDetails).toEqual({ count: 1 }))
    expect(store.phase).toBe('streaming')
    controlled.push({ event: 'token', data: { text: '' } })
    controlled.push({ event: 'token', data: { text: 'hello' } })
    controlled.push({ event: 'token', data: { text: 'world' } })
    await vi.waitFor(() => expect(store.draftAssistant).toBe('hello world'))
    const citation = { source_label: '[1]', document_id: 'd1', chunk_id: 'k1', quote: 'quote', page_number: 2, section: 'Intro', score: 0.8 }
    controlled.push({ event: 'citation', data: citation })
    controlled.push({ event: 'citation', data: { ...citation, quote: 'duplicate' } })
    await vi.waitFor(() => expect(store.citations).toHaveLength(1))
    controlled.push({ event: 'message_end', data: { content: 'final answer' } })
    controlled.end()
    await pending

    expect(store.phase).toBe('completed')
    expect(store.draftAssistant).toBe('final answer')
    expect(store.optimisticUser).toBeNull()
    expect(conversationsApi.messages).toHaveBeenCalledWith(conversationId)
    expect(conversations.messagesByConversation[conversationId]).toEqual(persistedMessages)
  })

  it('marks backend errors as failed while preserving partial output and enabling explicit retry', async () => {
    streamMock.mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'token', data: { text: 'partial' } },
      { event: 'error', data: { message: 'backend failed' } },
    )).mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'message_end', data: { content: 'recovered' } },
    ))
    const store = useChatStore()

    await store.send(conversationId, 'question')

    expect(store.phase).toBe('failed')
    expect(store.error).toBe('backend failed')
    expect(store.draftAssistant).toBe('partial')
    await store.retry(conversationId)
    expect(streamMock).toHaveBeenNthCalledWith(2, conversationId, 'question', expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(store.phase).toBe('completed')
    expect(store.draftAssistant).toBe('recovered')
  })

  it('cancels without retrying, preserves received content, and allows only a later explicit retry', async () => {
    const controlled = new ControlledEvents()
    streamMock.mockReturnValueOnce(controlled).mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'message_end', data: { content: 'retried' } },
    ))
    const store = useChatStore()
    const pending = store.send(conversationId, 'question')
    controlled.push({ event: 'token', data: { text: 'visible' } })
    await vi.waitFor(() => expect(store.draftAssistant).toBe('visible'))

    store.cancel()

    expect(store.phase).toBe('cancelled')
    expect(store.error).toBeNull()
    expect(store.draftAssistant).toBe('visible')
    expect(streamMock).toHaveBeenCalledTimes(1)
    await store.retry(conversationId)
    expect(streamMock).toHaveBeenCalledTimes(2)
    controlled.end()
    await pending
    expect(store.phase).toBe('completed')
    expect(store.draftAssistant).toBe('retried')
  })

  it('prevents stale generations from changing state or refreshing the wrong conversation', async () => {
    const stale = new ControlledEvents()
    streamMock.mockReturnValueOnce(stale).mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: secondConversationId } },
      { event: 'message_end', data: { content: 'new answer' } },
    ))
    const store = useChatStore()
    const oldPending = store.send(conversationId, 'old question')
    store.cancel()
    const newestPending = store.send(secondConversationId, 'new question')
    await newestPending
    stale.push({ event: 'token', data: { text: 'old' } })
    stale.push({ event: 'message_end', data: { content: 'old answer' } })
    stale.end()
    await oldPending

    expect(store.draftAssistant).toBe('new answer')
    expect(conversationsApi.messages).toHaveBeenCalledWith(secondConversationId)
    expect(conversationsApi.messages).not.toHaveBeenCalledWith(conversationId)
  })

  it('keeps completed output and the optimistic message visible when persisted refresh fails', async () => {
    conversationsApi.messages.mockRejectedValue(new Error('refresh failed'))
    streamMock.mockReturnValue(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'message_end', data: { content: 'authoritative' } },
    ))
    const store = useChatStore()

    await store.send(conversationId, 'question')

    expect(store.phase).toBe('completed')
    expect(store.draftAssistant).toBe('authoritative')
    expect(store.error).toBe('refresh failed')
    expect(store.optimisticUser).toEqual({ conversationId, content: 'question' })
  })

  it('rejects retry before a failed or cancelled message and while a stream is active', async () => {
    const controlled = new ControlledEvents()
    streamMock.mockReturnValue(controlled)
    const store = useChatStore()

    await expect(store.retry(conversationId)).rejects.toThrow('没有可重试的消息')
    const pending = store.send(conversationId, 'question')
    await expect(store.retry(conversationId)).rejects.toThrow('消息正在生成中')
    store.cancel()
    controlled.end()
    await pending
  })

  it('rejects retry when the requested conversation is not the failed conversation', async () => {
    streamMock.mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'error', data: { message: 'failed A' } },
    )).mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'message_end', data: { content: 'wrong retry' } },
    ))
    const store = useChatStore()
    await store.send(conversationId, 'question A')

    await expect(Reflect.apply(store.retry, store, [secondConversationId])).rejects.toThrow('当前会话没有可重试的消息')
    expect(streamMock).toHaveBeenCalledTimes(1)
  })

  it('clears backend running status after a terminal message_end', async () => {
    streamMock.mockReturnValue(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'agent_status', data: { status: 'running' } },
      { event: 'message_end', data: { content: 'done' } },
    ))
    const store = useChatStore()

    await store.send(conversationId, 'question')

    expect(store.phase).toBe('completed')
    expect(store.status).toBeNull()
  })

  it('stays busy until authoritative message refresh finishes after message_end', async () => {
    let resolveMessages!: (messages: typeof persistedMessages) => void
    conversationsApi.messages.mockReturnValue(new Promise((resolve) => { resolveMessages = resolve }))
    streamMock.mockReturnValue(events(
      { event: 'message_start', data: { conversation_id: conversationId } },
      { event: 'message_end', data: { content: 'done' } },
    ))
    const store = useChatStore()

    const pending = store.send(conversationId, 'question')
    await vi.waitFor(() => expect(store.phase).toBe('completed'))

    expect((store as unknown as { busy: boolean }).busy).toBe(true)
    resolveMessages(persistedMessages)
    await pending
    expect((store as unknown as { busy: boolean }).busy).toBe(false)
  })
})
