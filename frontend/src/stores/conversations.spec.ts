import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ConversationCreateDialog from '@/components/conversations/ConversationCreateDialog.vue'
import ConversationList from '@/components/conversations/ConversationList.vue'
import ChatPage from '@/pages/ChatPage.vue'
import { useConversationStore } from './conversations'
import { useKnowledgeBaseStore } from './knowledge-bases'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  get: vi.fn(),
  delete: vi.fn(),
  messages: vi.fn(),
}))

const knowledgeBasesApi = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('@/api/resources', () => ({ conversationsApi: api, knowledgeBasesApi }))

const firstConversationId = '11111111-1111-4111-8111-111111111111'
const secondConversationId = '22222222-2222-4222-8222-222222222222'
const knowledgeBase = {
  id: 'knowledge-base-1', name: '产品知识库', description: '', embedding_model: 'bge-m3', embedding_dimension: 1024,
  created_at: '2026-08-14T00:00:00Z', updated_at: '2026-08-14T00:00:00Z',
}

const firstConversation = {
  id: firstConversationId,
  knowledge_base_id: 'knowledge-base-1',
  title: '产品讨论',
  created_at: '2026-08-14T00:00:00Z',
  updated_at: '2026-08-14T00:00:00Z',
}

const secondConversation = {
  id: secondConversationId,
  knowledge_base_id: 'knowledge-base-2',
  title: '技术讨论',
  created_at: '2026-08-14T01:00:00Z',
  updated_at: '2026-08-14T01:00:00Z',
}

describe('conversation store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    knowledgeBasesApi.list.mockResolvedValue([])
  })

  it('keeps cached conversation lists scoped to their knowledge base', async () => {
    api.list.mockResolvedValueOnce([firstConversation]).mockResolvedValueOnce([secondConversation])
    const store = useConversationStore()

    await store.loadForKnowledgeBase('knowledge-base-1')
    await store.loadForKnowledgeBase('knowledge-base-2')
    await store.loadForKnowledgeBase('knowledge-base-1')

    expect(store.itemsByKnowledgeBase['knowledge-base-1']).toEqual([firstConversation])
    expect(store.itemsByKnowledgeBase['knowledge-base-2']).toEqual([secondConversation])
    expect(api.list).toHaveBeenCalledTimes(2)
  })

  it('orders persisted messages chronologically while preserving server order for matching timestamps', async () => {
    api.messages.mockResolvedValue([
      { id: 'third', conversation_id: firstConversationId, role: 'assistant', content: '第三条', status: 'complete', created_at: '2026-08-14T10:01:00Z', token_count: null, citations: [] },
      { id: 'first', conversation_id: firstConversationId, role: 'user', content: '第一条', status: 'complete', created_at: '2026-08-14T10:00:00Z', token_count: null, citations: [] },
      { id: 'second', conversation_id: firstConversationId, role: 'assistant', content: '第二条', status: 'complete', created_at: '2026-08-14T10:00:00Z', token_count: null, citations: [] },
    ])
    const store = useConversationStore()

    await store.loadMessages(firstConversationId)

    expect(store.messagesByConversation[firstConversationId].map((message) => message.id)).toEqual(['first', 'second', 'third'])
  })

  it('adds a created conversation to its own cache and selects it', async () => {
    api.create.mockResolvedValue(firstConversation)
    const store = useConversationStore()

    await store.create('knowledge-base-1', '  产品讨论  ')

    expect(store.itemsByKnowledgeBase['knowledge-base-1']).toEqual([firstConversation])
    expect(store.currentId).toBe(firstConversationId)
  })

  it('removes a conversation, its messages, and its current selection', async () => {
    api.list.mockResolvedValue([firstConversation])
    api.messages.mockResolvedValue([])
    api.delete.mockResolvedValue(undefined)
    const store = useConversationStore()
    await store.loadForKnowledgeBase('knowledge-base-1')
    await store.loadMessages(firstConversationId)
    store.select(firstConversationId)

    await store.remove(firstConversationId)

    expect(store.itemsByKnowledgeBase['knowledge-base-1']).toEqual([])
    expect(store.messagesByConversation[firstConversationId]).toBeUndefined()
    expect(store.currentId).toBeNull()
  })
})

describe('conversation create dialog', () => {
  it('rejects blank and titles over 200 characters, then emits a trimmed 200-character title', async () => {
    const wrapper = mount(ConversationCreateDialog, { props: { open: true } })

    await wrapper.get('form').trigger('submit')
    expect(wrapper.text()).toContain('会话标题不能为空')

    await wrapper.get('input').setValue('x'.repeat(200))
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('create')?.[0]).toEqual(['x'.repeat(200)])

    await wrapper.get('input').setValue('x'.repeat(201))
    await wrapper.get('form').trigger('submit')
    expect(wrapper.text()).toContain('会话标题不能超过 200 个字符')
  })

  it('allows the store to create a 200-character title', async () => {
    setActivePinia(createPinia())
    api.create.mockResolvedValue(firstConversation)

    await useConversationStore().create('knowledge-base-1', 'x'.repeat(200))

    expect(api.create).toHaveBeenCalledWith('knowledge-base-1', { title: 'x'.repeat(200) })
  })

  it('closes without creating when cancelled', async () => {
    const wrapper = mount(ConversationCreateDialog, { props: { open: true } })

    await wrapper.get('button[type="button"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('create')).toBeUndefined()
  })
})

describe('conversation list', () => {
  it('shows message counts only after that conversation has loaded messages', async () => {
    const wrapper = mount(ConversationList, {
      props: {
        conversations: [firstConversation, secondConversation],
        messagesByConversation: { [firstConversationId]: [] },
      },
    })

    expect(wrapper.text()).toContain('0 条消息')
    expect(wrapper.text()).not.toContain('技术讨论 0 条消息')
  })

  it('does not expose conversation renaming', () => {
    const wrapper = mount(ConversationList, {
      props: { conversations: [firstConversation], messagesByConversation: {} },
    })

    expect(wrapper.text()).not.toContain('重命名')
  })
})

describe('chat route query behavior', () => {
  it('uses a conversation query to load and select a persisted conversation', async () => {
    setActivePinia(createPinia())
    knowledgeBasesApi.list.mockResolvedValue([])
    api.get.mockResolvedValue(firstConversation)
    api.messages.mockResolvedValue([])
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: ChatPage }],
    })
    await router.push(`/?conversation=${firstConversationId}`)
    await router.isReady()

    const wrapper = mount(ChatPage, { global: { plugins: [router] } })
    await vi.waitFor(() => expect(api.get).toHaveBeenCalledWith(firstConversationId))

    expect(useConversationStore().currentId).toBe(firstConversationId)
    expect(api.messages).toHaveBeenCalledWith(firstConversationId)
    expect(wrapper.text()).toContain('产品讨论')
  })

  it('keeps an invalid conversation query recoverable without requesting the API', async () => {
    setActivePinia(createPinia())
    knowledgeBasesApi.list.mockResolvedValue([])
    api.get.mockReset()
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: ChatPage }],
    })
    await router.push('/?conversation=not-a-uuid')
    await router.isReady()

    const wrapper = mount(ChatPage, { global: { plugins: [router] } })
    await vi.waitFor(() => expect(wrapper.text()).toContain('会话不存在或已失效'))

    expect(api.get).not.toHaveBeenCalled()
  })

  it('keeps the newest conversation selected when an older route request finishes last', async () => {
    setActivePinia(createPinia())
    knowledgeBasesApi.list.mockResolvedValue([])
    let resolveFirstGet!: (value: typeof firstConversation) => void
    let resolveFirstMessages!: (value: []) => void
    let resolveSecondMessages!: (value: []) => void
    const firstGet = new Promise<typeof firstConversation>((resolve) => { resolveFirstGet = resolve })
    const firstMessages = new Promise<[]>((resolve) => { resolveFirstMessages = resolve })
    const secondMessages = new Promise<[]>((resolve) => { resolveSecondMessages = resolve })
    api.get.mockImplementation((id: string) => id === firstConversationId ? firstGet : Promise.resolve(secondConversation))
    api.messages.mockImplementation((id: string) => id === firstConversationId ? firstMessages : secondMessages)
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: ChatPage }] })
    await router.push(`/?conversation=${firstConversationId}`)
    await router.isReady()
    const wrapper = mount(ChatPage, { global: { plugins: [router] } })
    await vi.waitFor(() => expect(api.get).toHaveBeenCalledWith(firstConversationId))

    await router.push(`/?conversation=${secondConversationId}`)
    await vi.waitFor(() => expect(api.get).toHaveBeenCalledWith(secondConversationId))
    resolveSecondMessages([])
    await vi.waitFor(() => expect(wrapper.text()).toContain('技术讨论'))
    resolveFirstGet(firstConversation)
    await vi.waitFor(() => expect(api.messages).toHaveBeenCalledWith(firstConversationId))
    resolveFirstMessages([])
    await vi.waitFor(() => expect(useConversationStore().currentId).toBe(secondConversationId))

    expect(wrapper.text()).toContain('技术讨论')
  })

  it('keeps the new-conversation flow open when an older conversation request finishes', async () => {
    setActivePinia(createPinia())
    knowledgeBasesApi.list.mockResolvedValue([knowledgeBase])
    let resolveGet!: (value: typeof firstConversation) => void
    let resolveMessages!: (value: []) => void
    const delayedGet = new Promise<typeof firstConversation>((resolve) => { resolveGet = resolve })
    const delayedMessages = new Promise<[]>((resolve) => { resolveMessages = resolve })
    api.get.mockResolvedValue(delayedGet)
    api.messages.mockResolvedValue(delayedMessages)
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: ChatPage }] })
    await router.push(`/?conversation=${firstConversationId}`)
    await router.isReady()
    const wrapper = mount(ChatPage, { global: { plugins: [router] } })
    await vi.waitFor(() => expect(api.get).toHaveBeenCalledWith(firstConversationId))

    await router.push('/?new=1')
    await vi.waitFor(() => expect(wrapper.find('input').exists()).toBe(true))
    resolveGet(firstConversation)
    await vi.waitFor(() => expect(api.messages).toHaveBeenCalledWith(firstConversationId))
    resolveMessages([])
    await vi.waitFor(() => expect(useConversationStore().currentId).toBeNull())

    expect(wrapper.find('input').exists()).toBe(true)
  })

  it('creates from the new route and replaces it with the persisted conversation query', async () => {
    setActivePinia(createPinia())
    const knowledgeBases = useKnowledgeBaseStore()
    knowledgeBases.items = [knowledgeBase]
    knowledgeBases.select(knowledgeBase.id)
    api.create.mockResolvedValue(firstConversation)
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: ChatPage }] })
    const replace = vi.spyOn(router, 'replace')
    await router.push('/?new=1')
    await router.isReady()
    const wrapper = mount(ChatPage, { global: { plugins: [router] } })
    await vi.waitFor(() => expect(wrapper.find('input').exists()).toBe(true))

    await wrapper.get('input').setValue('新会话')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith({ name: 'chat', query: { conversation: firstConversationId } }))
  })
})
