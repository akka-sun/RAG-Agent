import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { streamConversationMessage, type CitationData, type SseEvent } from '@/api/sse'
import { useConversationStore } from './conversations'

export type ChatPhase = 'idle' | 'sending' | 'streaming' | 'retrieving' | 'completed' | 'failed' | 'cancelled'

export interface OptimisticUserMessage {
  conversationId: string
  content: string
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '消息发送失败，请稍后重试。'
}

function abortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
    || error instanceof Error && error.name === 'AbortError'
}

export const useChatStore = defineStore('chat', () => {
  const conversationStore = useConversationStore()
  const draftAssistant = ref('')
  const phase = ref<ChatPhase>('idle')
  const citations = ref<CitationData[]>([])
  const error = ref<string | null>(null)
  const syncError = ref<string | null>(null)
  const syncingMessages = ref(false)
  const status = ref<string | null>(null)
  const retrievalDetails = ref<Record<string, unknown> | null>(null)
  const optimisticUser = ref<OptimisticUserMessage | null>(null)
  const lastSubmittedContent = ref<string | null>(null)
  const lastConversationId = ref<string | null>(null)
  const submissionBaselineMessageIds = ref<string[]>([])
  const controller = shallowRef<AbortController | null>(null)
  const busy = computed(() => controller.value !== null)
  let generation = 0
  let syncGeneration = 0
  let retryable = false

  async function send(conversationId: string, content: string): Promise<void> {
    if (controller.value) throw new Error('消息正在生成中')
    const normalized = content.trim()
    if (!normalized) throw new Error('消息不能为空')
    lastConversationId.value = conversationId
    lastSubmittedContent.value = normalized
    submissionBaselineMessageIds.value = (conversationStore.messagesByConversation[conversationId] ?? [])
      .map((message) => message.id)
    optimisticUser.value = { conversationId, content: normalized }
    retryable = false
    await run(conversationId, normalized)
  }

  function cancel(): void {
    if (!controller.value) return
    generation += 1
    controller.value.abort()
    controller.value = null
    phase.value = 'cancelled'
    error.value = null
    status.value = null
    retryable = true
  }

  async function retry(conversationId: string): Promise<void> {
    if (controller.value) throw new Error('消息正在生成中')
    if (lastConversationId.value !== conversationId) throw new Error('当前会话没有可重试的消息')
    if (!retryable || !lastConversationId.value || !lastSubmittedContent.value) {
      throw new Error('没有可重试的消息')
    }
    retryable = false
    optimisticUser.value = {
      conversationId: lastConversationId.value,
      content: lastSubmittedContent.value,
    }
    await run(lastConversationId.value, lastSubmittedContent.value)
  }

  async function run(conversationId: string, content: string): Promise<void> {
    const activeGeneration = ++generation
    const activeController = new AbortController()
    controller.value = activeController
    draftAssistant.value = ''
    phase.value = 'sending'
    citations.value = []
    error.value = null
    syncError.value = null
    status.value = null
    retrievalDetails.value = null

    const isCurrent = () => generation === activeGeneration
    let terminalEventReceived = false
    try {
      for await (const event of streamConversationMessage(conversationId, content, { signal: activeController.signal })) {
        if (!isCurrent()) break
        const stop = await reduce(event, conversationId, isCurrent)
        if (stop) {
          terminalEventReceived = true
          break
        }
      }
      if (isCurrent() && !terminalEventReceived) {
        phase.value = 'failed'
        error.value = '连接提前结束，请重试。'
        status.value = null
        retryable = true
      }
    } catch (reason) {
      if (!isCurrent()) return
      if (activeController.signal.aborted || abortError(reason)) {
        phase.value = 'cancelled'
        error.value = null
      } else {
        phase.value = 'failed'
        error.value = errorMessage(reason)
      }
      status.value = null
      retryable = true
    } finally {
      if (isCurrent()) controller.value = null
    }
  }

  function reconcilePersisted(conversationId: string): boolean {
    if (conversationId !== lastConversationId.value || phase.value !== 'completed') return false
    const baseline = new Set(submissionBaselineMessageIds.value)
    const currentMessages = conversationStore.messagesByConversation[conversationId] ?? []
    let authoritativeUserSeen = false
    let authoritativePairSeen = false
    for (const message of currentMessages) {
      if (baseline.has(message.id)) continue
      if (!authoritativeUserSeen && message.role === 'user') {
        authoritativeUserSeen = true
      } else if (authoritativeUserSeen && message.role === 'assistant') {
        authoritativePairSeen = true
        break
      }
    }
    if (!authoritativePairSeen) return false
    optimisticUser.value = null
    draftAssistant.value = ''
    citations.value = []
    error.value = null
    syncError.value = null
    return true
  }

  async function reloadPersistedMessages(
    conversationId: string,
    isCurrent: () => boolean = () => true,
  ): Promise<boolean> {
    if (conversationId !== lastConversationId.value || phase.value !== 'completed') return false
    const activeSyncGeneration = ++syncGeneration
    syncingMessages.value = true
    try {
      await conversationStore.loadMessages(conversationId, isCurrent)
      if (!isCurrent()) return false
      const reconciled = reconcilePersisted(conversationId)
      if (!reconciled) syncError.value = '服务器消息尚未同步完成，请重新加载消息。'
      return reconciled
    } catch (reason) {
      if (!isCurrent()) return false
      conversationStore.error = null
      syncError.value = errorMessage(reason)
      return false
    } finally {
      if (activeSyncGeneration === syncGeneration) syncingMessages.value = false
    }
  }

  async function reduce(event: SseEvent, conversationId: string, isCurrent: () => boolean): Promise<boolean> {
    switch (event.event) {
      case 'message_start':
        phase.value = 'streaming'
        break
      case 'agent_status':
        status.value = event.data.status
        break
      case 'retrieval_start':
        phase.value = 'retrieving'
        retrievalDetails.value = event.data
        break
      case 'retrieval_result':
        phase.value = 'streaming'
        retrievalDetails.value = event.data
        break
      case 'token': {
        const token = event.data.text.trim()
        if (token) draftAssistant.value += `${draftAssistant.value ? ' ' : ''}${token}`
        break
      }
      case 'citation': {
        const duplicate = citations.value.some((citation) => citation.source_label === event.data.source_label
          && citation.chunk_id === event.data.chunk_id)
        if (!duplicate) citations.value.push(event.data)
        break
      }
      case 'error':
        phase.value = 'failed'
        error.value = event.data.message
        status.value = null
        retryable = true
        return true
      case 'message_end':
        draftAssistant.value = event.data.content
        phase.value = 'completed'
        status.value = null
        retryable = false
        await reloadPersistedMessages(conversationId, isCurrent)
        return true
    }
    return false
  }

  return {
    draftAssistant,
    phase,
    citations,
    error,
    syncError,
    syncingMessages,
    status,
    retrievalDetails,
    optimisticUser,
    lastSubmittedContent,
    lastConversationId,
    submissionBaselineMessageIds,
    busy,
    reconcilePersisted,
    reloadPersistedMessages,
    send,
    cancel,
    retry,
  }
})
