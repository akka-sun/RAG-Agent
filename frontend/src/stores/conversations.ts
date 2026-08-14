import { ref } from 'vue'
import { defineStore } from 'pinia'
import { conversationsApi } from '@/api/resources'
import type { Conversation, Message } from '@/types/api'

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请稍后重试。'
}

function validTitle(title: string): string {
  const trimmed = title.trim()
  if (!trimmed) throw new Error('会话标题不能为空')
  if (trimmed.length > 200) throw new Error('会话标题不能超过 200 个字符')
  return trimmed
}

function sortMessages(messages: Message[]): Message[] {
  return messages
    .map((message, index) => ({ message, index }))
    .sort((left, right) => {
      const chronological = Date.parse(left.message.created_at) - Date.parse(right.message.created_at)
      return Number.isNaN(chronological) || chronological === 0 ? left.index - right.index : chronological
    })
    .map(({ message }) => message)
}

export const useConversationStore = defineStore('conversations', () => {
  const itemsByKnowledgeBase = ref<Record<string, Conversation[]>>({})
  const messagesByConversation = ref<Record<string, Message[]>>({})
  const currentId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadForKnowledgeBase(knowledgeBaseId: string): Promise<void> {
    if (Object.hasOwn(itemsByKnowledgeBase.value, knowledgeBaseId)) return
    loading.value = true
    error.value = null
    try {
      itemsByKnowledgeBase.value[knowledgeBaseId] = await conversationsApi.list(knowledgeBaseId) ?? []
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    } finally {
      loading.value = false
    }
  }

  async function create(knowledgeBaseId: string, title: string): Promise<Conversation> {
    error.value = null
    try {
      const item = await conversationsApi.create(knowledgeBaseId, { title: validTitle(title) })
      if (!item) throw new Error('会话创建失败，请稍后重试。')
      const items = itemsByKnowledgeBase.value[knowledgeBaseId] ?? []
      itemsByKnowledgeBase.value[knowledgeBaseId] = [...items, item]
      currentId.value = item.id
      return item
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    }
  }

  function select(id: string | null): void {
    currentId.value = id
  }

  async function loadMessages(conversationId: string, isCurrent: () => boolean = () => true): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const messages = await conversationsApi.messages(conversationId) ?? []
      if (!isCurrent()) return
      messagesByConversation.value[conversationId] = sortMessages(messages)
    } catch (reason) {
      if (!isCurrent()) return
      error.value = messageFor(reason)
      throw reason
    } finally {
      if (isCurrent()) loading.value = false
    }
  }

  async function remove(conversationId: string): Promise<void> {
    error.value = null
    try {
      await conversationsApi.delete(conversationId)
      for (const knowledgeBaseId of Object.keys(itemsByKnowledgeBase.value)) {
        itemsByKnowledgeBase.value[knowledgeBaseId] = itemsByKnowledgeBase.value[knowledgeBaseId]
          .filter((conversation) => conversation.id !== conversationId)
      }
      delete messagesByConversation.value[conversationId]
      if (currentId.value === conversationId) currentId.value = null
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    }
  }

  return {
    itemsByKnowledgeBase,
    messagesByConversation,
    currentId,
    loading,
    error,
    loadForKnowledgeBase,
    create,
    select,
    loadMessages,
    remove,
  }
})
