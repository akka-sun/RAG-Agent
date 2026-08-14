import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { knowledgeBasesApi } from '@/api/resources'
import type { KnowledgeBase, KnowledgeBaseCreate } from '@/types/api'

const selectedKnowledgeBaseKey = 'rag-agent:selected-kb'

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请稍后重试。'
}

export const useKnowledgeBaseStore = defineStore('knowledge-bases', () => {
  const items = ref<KnowledgeBase[]>([])
  const selectedId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selected = computed(() => items.value.find((item) => item.id === selectedId.value) ?? null)

  function select(id: string | null): void {
    selectedId.value = id
    if (id === null) {
      localStorage.removeItem(selectedKnowledgeBaseKey)
    } else {
      localStorage.setItem(selectedKnowledgeBaseKey, id)
    }
  }

  async function load(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      items.value = await knowledgeBasesApi.list() ?? []
      const savedId = selectedId.value ?? localStorage.getItem(selectedKnowledgeBaseKey)
      const validId = savedId && items.value.some((item) => item.id === savedId) ? savedId : null

      if (validId) {
        select(validId)
      } else {
        select(items.value[0]?.id ?? null)
      }
    } catch (reason) {
      error.value = messageFor(reason)
    } finally {
      loading.value = false
    }
  }

  async function create(input: KnowledgeBaseCreate): Promise<KnowledgeBase> {
    error.value = null
    try {
      const item = await knowledgeBasesApi.create(input)
      if (!item) throw new Error('知识库创建失败，请稍后重试。')
      items.value.push(item)
      select(item.id)
      return item
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    }
  }

  async function remove(id: string): Promise<void> {
    error.value = null
    try {
      await knowledgeBasesApi.delete(id)
      items.value = items.value.filter((item) => item.id !== id)
      if (selectedId.value === id) select(items.value[0]?.id ?? null)
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    }
  }

  return { items, selectedId, selected, loading, error, load, select, create, remove }
})
