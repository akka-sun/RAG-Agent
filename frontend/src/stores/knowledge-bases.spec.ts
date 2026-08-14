import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useKnowledgeBaseStore } from './knowledge-bases'
import KnowledgeBaseForm from '@/components/knowledge-base/KnowledgeBaseForm.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/resources', () => ({ knowledgeBasesApi: api }))

const knowledgeBases = [
  {
    id: 'first-id',
    name: '产品文档',
    description: '团队产品资料',
    embedding_model: 'text-embedding-3-large',
    embedding_dimension: 3072,
    created_at: '2026-08-14T00:00:00Z',
    updated_at: '2026-08-14T01:00:00Z',
  },
  {
    id: 'second-id',
    name: '技术规范',
    description: '',
    embedding_model: 'bge-m3',
    embedding_dimension: 1024,
    created_at: '2026-08-13T00:00:00Z',
    updated_at: '2026-08-13T01:00:00Z',
  },
]

describe('knowledge-base store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('persists the selected knowledge-base ID', () => {
    const store = useKnowledgeBaseStore()

    store.select('knowledge-base-id')

    expect(localStorage.getItem('rag-agent:selected-kb')).toBe('knowledge-base-id')
    expect(store.selectedId).toBe('knowledge-base-id')
  })

  it('replaces a stale saved selection with the first loaded knowledge base', async () => {
    localStorage.setItem('rag-agent:selected-kb', 'missing-id')
    api.list.mockResolvedValue(knowledgeBases)
    const store = useKnowledgeBaseStore()

    await store.load()

    expect(store.selectedId).toBe('first-id')
    expect(store.selected).toEqual(knowledgeBases[0])
    expect(localStorage.getItem('rag-agent:selected-kb')).toBe('first-id')
  })

  it('selects the first loaded knowledge base when there is no saved selection', async () => {
    api.list.mockResolvedValue(knowledgeBases)
    const store = useKnowledgeBaseStore()

    await store.load()

    expect(store.selectedId).toBe('first-id')
  })

  it('clears selection when the loaded knowledge-base list is empty', async () => {
    localStorage.setItem('rag-agent:selected-kb', 'first-id')
    api.list.mockResolvedValue([])
    const store = useKnowledgeBaseStore()

    await store.load()

    expect(store.selectedId).toBeNull()
    expect(store.selected).toBeNull()
    expect(localStorage.getItem('rag-agent:selected-kb')).toBeNull()
  })

  it('treats an empty list response as no knowledge bases', async () => {
    api.list.mockResolvedValue(undefined)
    const store = useKnowledgeBaseStore()

    await store.load()

    expect(store.items).toEqual([])
    expect(store.selectedId).toBeNull()
  })

  it('selects a newly created knowledge base', async () => {
    api.create.mockResolvedValue(knowledgeBases[1])
    const store = useKnowledgeBaseStore()

    await store.create({
      name: '技术规范', description: '',
    })

    expect(store.items).toEqual([knowledgeBases[1]])
    expect(store.selectedId).toBe('second-id')
  })

  it('recovers the selection after deleting the selected knowledge base', async () => {
    api.list.mockResolvedValue(knowledgeBases)
    api.delete.mockResolvedValue(undefined)
    const store = useKnowledgeBaseStore()
    await store.load()

    await store.remove('first-id')

    expect(store.items).toEqual([knowledgeBases[1]])
    expect(store.selectedId).toBe('second-id')
  })
})

describe('knowledge-base form', () => {
  it('requires a nonblank name', async () => {
    const wrapper = mount(KnowledgeBaseForm)

    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('知识库名称不能为空')
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('submits only name and description without embedding settings', async () => {
    const wrapper = mount(KnowledgeBaseForm)

    expect(wrapper.find('#knowledge-base-model').exists()).toBe(false)
    expect(wrapper.find('#knowledge-base-dimension').exists()).toBe(false)

    await wrapper.get('#knowledge-base-name').setValue('  Product docs ')
    await wrapper.get('#knowledge-base-description').setValue('Team references')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')).toEqual([[{ name: 'Product docs', description: 'Team references' }]])
  })
})

describe('knowledge-base deletion confirmation', () => {
  it('warns that documents, conversations, and indexes will also be removed', () => {
    const wrapper = mount(ConfirmDialog, {
      props: { open: true, title: '删除知识库', confirmLabel: '删除' },
    })

    expect(wrapper.text()).toContain('关联的文档、会话和索引也会被移除')
  })
})
