import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SseEvent } from '@/api/sse'
import { useChatStore } from '@/stores/chat'
import { useKnowledgeBaseStore } from '@/stores/knowledge-bases'
import ChatPage from './ChatPage.vue'

const streamMock = vi.hoisted(() => vi.fn())
const conversationsApi = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), get: vi.fn(), delete: vi.fn(), messages: vi.fn(),
}))
const knowledgeBasesApi = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('@/api/sse', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/sse')>(),
  streamConversationMessage: streamMock,
}))
vi.mock('@/api/resources', () => ({ conversationsApi, knowledgeBasesApi }))

class ControlledEvents implements AsyncIterable<SseEvent>, AsyncIterator<SseEvent> {
  private queued: IteratorResult<SseEvent>[] = []
  private waiting?: (value: IteratorResult<SseEvent>) => void
  [Symbol.asyncIterator](): AsyncIterator<SseEvent> { return this }
  next(): Promise<IteratorResult<SseEvent>> {
    const queued = this.queued.shift()
    if (queued) return Promise.resolve(queued)
    return new Promise((resolve) => { this.waiting = resolve })
  }
  push(event: SseEvent): void { this.deliver({ value: event, done: false }) }
  end(): void { this.deliver({ value: undefined, done: true }) }
  private deliver(value: IteratorResult<SseEvent>): void {
    if (this.waiting) {
      const resolve = this.waiting
      this.waiting = undefined
      resolve(value)
    } else {
      this.queued.push(value)
    }
  }
}

function events(...items: SseEvent[]): AsyncIterable<SseEvent> {
  return (async function* () { yield* items })()
}

const knowledgeBases = [
  { id: 'kb-1', name: '产品库', description: '', embedding_model: 'bge-m3', embedding_dimension: 1024, created_at: '', updated_at: '' },
  { id: 'kb-2', name: '技术库', description: '', embedding_model: 'bge-m3', embedding_dimension: 1024, created_at: '', updated_at: '' },
]
const conversation = {
  id: '11111111-1111-4111-8111-111111111111', knowledge_base_id: 'kb-1', title: '部署讨论', created_at: '', updated_at: '',
}
const secondConversation = {
  id: '22222222-2222-4222-8222-222222222222', knowledge_base_id: 'kb-2', title: '技术讨论', created_at: '', updated_at: '',
}
const persistedMessages = [
  { id: 'u1', conversation_id: conversation.id, role: 'user', content: '如何部署？', status: 'completed', created_at: '2026-08-14T00:00:00Z', token_count: null, citations: [] },
  { id: 'a1', conversation_id: conversation.id, role: 'assistant', content: '使用容器。', status: 'completed', created_at: '2026-08-14T00:00:01Z', token_count: null, citations: [] },
]

async function mountPage() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', name: 'chat', component: ChatPage }, { path: '/conversations', name: 'conversations', component: { template: '<div />' } }] })
  await router.push(`/?conversation=${conversation.id}`)
  await router.isReady()
  const wrapper = mount(ChatPage, { attachTo: document.body, global: { plugins: [router] } })
  await vi.waitFor(() => expect(conversationsApi.get).toHaveBeenCalledWith(conversation.id))
  await vi.waitFor(() => expect(wrapper.text()).toContain('部署讨论'))
  return { wrapper, router }
}

describe('ChatPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    const store = useKnowledgeBaseStore()
    store.items = knowledgeBases
    store.select('kb-1')
    conversationsApi.get.mockResolvedValue(conversation)
    conversationsApi.messages.mockResolvedValue([])
    conversationsApi.list.mockResolvedValue([])
  })
  afterEach(() => document.body.replaceChildren())

  it('uses the responsive chat-first structure and loads conversations when the KB changes', async () => {
    const { wrapper } = await mountPage()
    expect(wrapper.find('.chat-layout').exists()).toBe(true)
    expect(wrapper.find('.chat-layout__conversation-rail').exists()).toBe(true)
    expect(wrapper.find('.chat-layout__main').exists()).toBe(true)

    await wrapper.get('select[aria-label="当前知识库"]').setValue('kb-2')
    await vi.waitFor(() => expect(conversationsApi.list).toHaveBeenCalledWith('kb-2'))
    expect(useKnowledgeBaseStore().selectedId).toBe('kb-2')
  })

  it('wires send, cancel, and explicit retry through the active conversation', async () => {
    const controlled = new ControlledEvents()
    streamMock.mockReturnValueOnce(controlled).mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: conversation.id } },
      { event: 'message_end', data: { content: '重试成功' } },
    ))
    const { wrapper } = await mountPage()

    await wrapper.get('textarea').setValue('如何部署？')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(streamMock).toHaveBeenCalledTimes(1))
    expect(streamMock).toHaveBeenCalledWith(conversation.id, '如何部署？', expect.objectContaining({ signal: expect.any(AbortSignal) }))

    await wrapper.get('button[aria-label="停止生成"]').trigger('click')
    controlled.end()
    await vi.waitFor(() => expect(wrapper.find('button[aria-label="重试上一条消息"]').exists()).toBe(true))
    await wrapper.get('button[aria-label="重试上一条消息"]').trigger('click')
    await vi.waitFor(() => expect(streamMock).toHaveBeenCalledTimes(2))
  })

  it('hides failed state from conversation A after navigating to conversation B and rejects cross-conversation retry', async () => {
    streamMock.mockReturnValue(events(
      { event: 'message_start', data: { conversation_id: conversation.id } },
      { event: 'agent_status', data: { status: 'running' } },
      { event: 'error', data: { message: 'A failed' } },
    ))
    conversationsApi.get.mockImplementation((id: string) => Promise.resolve(id === secondConversation.id ? secondConversation : conversation))
    const { wrapper, router } = await mountPage()
    await wrapper.get('textarea').setValue('question A')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(wrapper.text()).toContain('A failed'))

    await router.push({ name: 'chat', query: { conversation: secondConversation.id } })
    await vi.waitFor(() => expect(wrapper.text()).toContain('技术讨论'))

    expect(wrapper.text()).not.toContain('A failed')
    expect(wrapper.find('button[aria-label="重试上一条消息"]').exists()).toBe(false)
    await expect(Reflect.apply(useChatStore().retry, useChatStore(), [secondConversation.id])).rejects.toThrow('当前会话没有可重试的消息')
    expect(streamMock).toHaveBeenCalledTimes(1)
  })

  it('hides cancelled state from conversation A after switching to another knowledge base', async () => {
    const controlled = new ControlledEvents()
    streamMock.mockReturnValue(controlled)
    const { wrapper } = await mountPage()
    await wrapper.get('textarea').setValue('question A')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(wrapper.find('button[aria-label="停止生成"]').exists()).toBe(true))
    await wrapper.get('button[aria-label="停止生成"]').trigger('click')
    controlled.end()
    await vi.waitFor(() => expect(wrapper.text()).toContain('生成已停止'))

    await wrapper.get('select[aria-label="当前知识库"]').setValue('kb-2')
    await vi.waitFor(() => expect(useKnowledgeBaseStore().selectedId).toBe('kb-2'))

    expect(wrapper.text()).not.toContain('生成已停止')
    expect(wrapper.find('button[aria-label="重试上一条消息"]').exists()).toBe(false)
    await expect(Reflect.apply(useChatStore().retry, useChatStore(), [secondConversation.id])).rejects.toThrow('当前会话没有可重试的消息')
    expect(streamMock).toHaveBeenCalledTimes(1)
  })

  it('keeps composer disabled while message_end refresh is pending', async () => {
    let resolveRefresh!: (messages: typeof persistedMessages) => void
    conversationsApi.messages.mockResolvedValueOnce([]).mockReturnValueOnce(new Promise((resolve) => { resolveRefresh = resolve }))
    streamMock.mockReturnValue(events(
      { event: 'message_start', data: { conversation_id: conversation.id } },
      { event: 'message_end', data: { content: '使用容器。' } },
    ))
    const { wrapper } = await mountPage()
    const textarea = wrapper.get('textarea')
    await textarea.setValue('如何部署？')
    await textarea.trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(useChatStore().phase).toBe('completed'))

    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    resolveRefresh(persistedMessages)
    await vi.waitFor(() => expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined())
  })

  it('reconciles only after route reload returns a new-ID user/assistant pair beyond the submission baseline', async () => {
    const newPersistedMessages = [
      ...persistedMessages,
      { ...persistedMessages[0], id: 'u2', created_at: '2026-08-14T00:00:02Z' },
      { ...persistedMessages[1], id: 'a2', created_at: '2026-08-14T00:00:03Z' },
    ]
    conversationsApi.messages
      .mockResolvedValueOnce(persistedMessages)
      .mockRejectedValueOnce(new Error('refresh failed'))
      .mockResolvedValueOnce(persistedMessages)
      .mockResolvedValueOnce(newPersistedMessages)
    streamMock.mockReturnValue(events(
      { event: 'message_start', data: { conversation_id: conversation.id } },
      { event: 'message_end', data: { content: '使用容器。' } },
    ))
    const { wrapper, router } = await mountPage()
    await wrapper.get('textarea').setValue('如何部署？')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(useChatStore().error).toBe('refresh failed'))
    expect(wrapper.findAll('[aria-label="你的消息"]')).toHaveLength(2)
    expect(wrapper.findAll('[aria-label="助手消息"]')).toHaveLength(2)

    await router.push({ name: 'chat' })
    await router.push({ name: 'chat', query: { conversation: conversation.id } })
    await vi.waitFor(() => expect(wrapper.text()).toContain('部署讨论'))
    await vi.waitFor(() => expect(conversationsApi.messages).toHaveBeenCalledTimes(3))
    expect(useChatStore().optimisticUser).not.toBeNull()
    expect(useChatStore().draftAssistant).toBe('使用容器。')
    expect(wrapper.findAll('[aria-label="你的消息"]')).toHaveLength(2)
    expect(wrapper.findAll('[aria-label="助手消息"]')).toHaveLength(2)

    await router.push({ name: 'chat' })
    await router.push({ name: 'chat', query: { conversation: conversation.id } })
    await vi.waitFor(() => expect(conversationsApi.messages).toHaveBeenCalledTimes(4))
    expect(useChatStore().optimisticUser).toBeNull()
    expect(useChatStore().draftAssistant).toBe('')
    expect(wrapper.findAll('[aria-label="你的消息"]')).toHaveLength(2)
    expect(wrapper.findAll('[aria-label="助手消息"]')).toHaveLength(2)
  })

  it('cancels active A during direct route resolution to B so B can send and stale A cannot pollute it', async () => {
    const activeA = new ControlledEvents()
    const persistedB = [
      { ...persistedMessages[0], id: 'bu1', conversation_id: secondConversation.id, content: 'question B' },
      { ...persistedMessages[1], id: 'ba1', conversation_id: secondConversation.id, content: 'B answer' },
    ]
    let bMessageLoads = 0
    conversationsApi.messages.mockImplementation((id: string) => {
      if (id !== secondConversation.id) return Promise.resolve([])
      bMessageLoads += 1
      return Promise.resolve(bMessageLoads === 1 ? [] : persistedB)
    })
    streamMock.mockReturnValueOnce(activeA).mockReturnValueOnce(events(
      { event: 'message_start', data: { conversation_id: secondConversation.id } },
      { event: 'message_end', data: { content: 'B answer' } },
    ))
    conversationsApi.get.mockImplementation((id: string) => Promise.resolve(id === secondConversation.id ? secondConversation : conversation))
    const { wrapper, router } = await mountPage()
    await wrapper.get('textarea').setValue('question A')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(streamMock).toHaveBeenCalledTimes(1))

    await router.push({ name: 'chat', query: { conversation: secondConversation.id } })
    await vi.waitFor(() => expect(wrapper.text()).toContain('技术讨论'))
    const firstSignal = streamMock.mock.calls[0][2].signal as AbortSignal
    expect(firstSignal.aborted).toBe(true)

    await wrapper.get('textarea').setValue('question B')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await vi.waitFor(() => expect(streamMock).toHaveBeenCalledTimes(2))
    expect(streamMock.mock.calls[1][0]).toBe(secondConversation.id)

    activeA.push({ event: 'token', data: { text: 'stale A' } })
    activeA.push({ event: 'message_end', data: { content: 'stale A answer' } })
    activeA.end()
    await vi.waitFor(() => expect(useChatStore().lastConversationId).toBe(secondConversation.id))
    await vi.waitFor(() => expect(wrapper.text()).toContain('B answer'))
    expect(wrapper.text()).not.toContain('stale A')
    expect(useChatStore().draftAssistant).toBe('')
  })

  it('closes the conversation rail before opening the new-chat title dialog', async () => {
    const { wrapper } = await mountPage()
    await wrapper.get('button[aria-label="打开会话历史"]').trigger('click')
    expect(wrapper.get('.chat-layout').classes()).toContain('chat-layout--rail-open')

    await wrapper.get('.chat-page__rail-header .button').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[role="dialog"]').exists()).toBe(true))

    expect(wrapper.get('.chat-layout').classes()).not.toContain('chat-layout--rail-open')
    expect(document.activeElement).toBe(wrapper.get('.conversation-create-dialog input').element)
  })
})
