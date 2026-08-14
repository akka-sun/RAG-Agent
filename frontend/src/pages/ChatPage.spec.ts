import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { SseEvent } from '@/api/sse'
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
  private waiting?: (value: IteratorResult<SseEvent>) => void
  [Symbol.asyncIterator](): AsyncIterator<SseEvent> { return this }
  next(): Promise<IteratorResult<SseEvent>> {
    return new Promise((resolve) => { this.waiting = resolve })
  }
  end(): void { this.waiting?.({ value: undefined, done: true }) }
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

async function mountPage() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', name: 'chat', component: ChatPage }, { path: '/conversations', name: 'conversations', component: { template: '<div />' } }] })
  await router.push(`/?conversation=${conversation.id}`)
  await router.isReady()
  const wrapper = mount(ChatPage, { global: { plugins: [router] } })
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
})
