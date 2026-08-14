<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { CitationData } from '@/api/sse'
import { conversationsApi } from '@/api/resources'
import { ApiError } from '@/api/client'
import AgentStatus from '@/components/chat/AgentStatus.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatHeader from '@/components/chat/ChatHeader.vue'
import CitationDrawer from '@/components/chat/CitationDrawer.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ConversationCreateDialog from '@/components/conversations/ConversationCreateDialog.vue'
import InlineAlert from '@/components/common/InlineAlert.vue'
import ChatLayout from '@/layouts/ChatLayout.vue'
import { useChatStore } from '@/stores/chat'
import { useConversationStore } from '@/stores/conversations'
import { useKnowledgeBaseStore } from '@/stores/knowledge-bases'
import type { Conversation, MessageCitation } from '@/types/api'

const route = useRoute()
const router = useRouter()
const chat = useChatStore()
const conversations = useConversationStore()
const knowledgeBases = useKnowledgeBaseStore()
const pageError = ref<string | null>(null)
const routeErrorKind = ref<'not-found' | 'error' | null>(null)
const loading = ref(false)
const creating = ref(false)
const createOpen = ref(false)
const railOpen = ref(false)
const conversation = ref<Conversation | null>(null)
const activeCitation = ref<MessageCitation | CitationData | null>(null)
const requestedConversationId = computed(() => typeof route.query.conversation === 'string' ? route.query.conversation : null)
const isNewFlow = computed(() => route.query.new === '1')
const currentConversations = computed(() => knowledgeBases.selectedId
  ? conversations.itemsByKnowledgeBase[knowledgeBases.selectedId] ?? []
  : [])
const messages = computed(() => conversation.value
  ? conversations.messagesByConversation[conversation.value.id] ?? []
  : [])
const currentChatState = computed(() => conversation.value !== null && chat.lastConversationId === conversation.value.id)
const visiblePhase = computed(() => currentChatState.value ? chat.phase : 'idle')
const visibleStatus = computed(() => currentChatState.value ? chat.status : null)
const visibleError = computed(() => currentChatState.value ? chat.error : null)
const visibleSyncError = computed(() => currentChatState.value ? chat.syncError : null)
const activeStream = computed(() => currentChatState.value && chat.busy)
const canRetry = computed(() => currentChatState.value && (chat.phase === 'failed' || chat.phase === 'cancelled'))
const draftForConversation = computed(() => conversation.value && chat.lastConversationId === conversation.value.id ? chat.draftAssistant : '')
const citationsForConversation = computed(() => conversation.value && chat.lastConversationId === conversation.value.id ? chat.citations : [])
const baselineForConversation = computed(() => conversation.value && chat.lastConversationId === conversation.value.id
  ? chat.submissionBaselineMessageIds
  : [])
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
let routeGeneration = 0

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '会话加载失败，请稍后重试。'
}

async function resolveRoute(): Promise<void> {
  const generation = ++routeGeneration
  const isCurrent = () => generation === routeGeneration
  const targetConversationId = isNewFlow.value ? null : requestedConversationId.value
  if (chat.busy && chat.lastConversationId !== targetConversationId) chat.cancel()
  pageError.value = null
  routeErrorKind.value = null
  conversation.value = null
  createOpen.value = false
  loading.value = false

  if (isNewFlow.value) {
    conversations.select(null)
    if (!knowledgeBases.selectedId) {
      pageError.value = '请先选择一个知识库，再创建会话。'
      return
    }
    createOpen.value = true
    return
  }

  const conversationId = requestedConversationId.value
  if (!conversationId) {
    conversations.select(null)
    pageError.value = knowledgeBases.selectedId ? '请选择已有会话，或创建一个新会话。' : '请先选择或创建知识库。'
    return
  }
  if (!uuidPattern.test(conversationId)) {
    conversations.select(null)
    pageError.value = '会话不存在或已失效，请从会话历史中重新选择。'
    routeErrorKind.value = 'not-found'
    return
  }

  loading.value = true
  try {
    const item = await conversationsApi.get(conversationId)
    if (!isCurrent()) return
    if (!item) throw new Error('会话不存在')
    knowledgeBases.select(item.knowledge_base_id)
    conversations.select(item.id)
    await conversations.loadForKnowledgeBase(item.knowledge_base_id)
    await conversations.loadMessages(item.id, isCurrent)
    if (!isCurrent()) return
    chat.reconcilePersisted(item.id)
    conversation.value = item
  } catch (reason) {
    if (!isCurrent()) return
    conversations.select(null)
    if (reason instanceof ApiError && reason.status === 404) {
      routeErrorKind.value = 'not-found'
      pageError.value = '会话不存在或已失效，请从会话历史中重新选择。'
    } else {
      routeErrorKind.value = 'error'
      pageError.value = errorMessage(reason)
    }
  } finally {
    if (isCurrent()) loading.value = false
  }
}

async function changeKnowledgeBase(id: string): Promise<void> {
  if (!id || id === knowledgeBases.selectedId) return
  if (activeStream.value) chat.cancel()
  knowledgeBases.select(id)
  conversations.select(null)
  conversation.value = null
  railOpen.value = true
  try {
    await conversations.loadForKnowledgeBase(id)
  } catch {
    // The store exposes the backend error below.
  }
  await router.push({ name: 'chat' })
}

async function selectConversation(id: string): Promise<void> {
  if (activeStream.value) chat.cancel()
  railOpen.value = false
  await router.push({ name: 'chat', query: { conversation: id } })
}

async function startNewChat(): Promise<void> {
  if (!knowledgeBases.selectedId) {
    pageError.value = '请先选择一个知识库，再创建会话。'
    return
  }
  if (activeStream.value) chat.cancel()
  railOpen.value = false
  await router.push({ name: 'chat', query: { new: '1' } })
}

async function create(title: string): Promise<void> {
  if (!knowledgeBases.selectedId) return
  creating.value = true
  try {
    const item = await conversations.create(knowledgeBases.selectedId, title)
    await router.replace({ name: 'chat', query: { conversation: item.id } })
  } catch {
    // The store exposes the backend error below.
  } finally {
    creating.value = false
  }
}

async function send(content: string, accept: () => void): Promise<void> {
  if (!conversation.value || !knowledgeBases.selectedId) return
  try {
    const conversationId = conversation.value.id
    const pending = chat.send(conversationId, content)
    if (chat.busy && chat.lastConversationId === conversationId) accept()
    await pending
  } catch {
    // The chat store exposes the backend error through AgentStatus.
  }
}

async function retry(): Promise<void> {
  if (!conversation.value) return
  try {
    await chat.retry(conversation.value.id)
  } catch {
    // Retry eligibility is reflected by the composer and store state.
  }
}

async function reloadMessages(): Promise<void> {
  if (!conversation.value) return
  await chat.reloadPersistedMessages(conversation.value.id)
}

onMounted(async () => {
  if (knowledgeBases.items.length === 0 && !knowledgeBases.loading) await knowledgeBases.load()
  if (knowledgeBases.selectedId) {
    try { await conversations.loadForKnowledgeBase(knowledgeBases.selectedId) } catch { /* shown by store */ }
  }
  await resolveRoute()
})
watch(() => route.query, resolveRoute)
</script>

<template>
  <ChatLayout :rail-open="railOpen" @close-rail="railOpen = false">
    <template #rail>
      <div class="chat-page__rail-header">
        <strong>会话历史</strong>
        <button type="button" class="button" @click="startNewChat">新建</button>
      </div>
      <p v-if="conversations.loading && currentConversations.length === 0" role="status">正在加载会话…</p>
      <p v-else-if="!knowledgeBases.selectedId" class="chat-page__rail-empty">选择知识库后查看会话。</p>
      <p v-else-if="currentConversations.length === 0" class="chat-page__rail-empty">还没有会话，创建一个开始提问。</p>
      <ul v-else class="chat-page__conversations">
        <li v-for="item in currentConversations" :key="item.id">
          <button type="button" :aria-current="item.id === conversation?.id ? 'page' : undefined" @click="selectConversation(item.id)">{{ item.title }}</button>
        </li>
      </ul>
    </template>

    <ChatHeader
      :title="conversation?.title ?? '新对话'"
      :knowledge-bases="knowledgeBases.items"
      :selected-knowledge-base-id="knowledgeBases.selectedId"
      :rail-open="railOpen"
      @select-knowledge-base="changeKnowledgeBase"
      @toggle-rail="railOpen = !railOpen"
      @new-chat="startNewChat"
    />

    <div class="chat-page__body">
      <div v-if="pageError && routeErrorKind" class="chat-page__route-error">
        <InlineAlert :message="pageError" />
        <div class="chat-page__route-error-actions">
          <button
            v-if="routeErrorKind === 'error'"
            name="retry-conversation"
            type="button"
            class="button button--secondary"
            @click="resolveRoute"
          >重试</button>
          <RouterLink class="button button--secondary" :to="{ name: 'conversations' }">返回会话列表</RouterLink>
        </div>
      </div>
      <InlineAlert v-else-if="pageError || conversations.error || knowledgeBases.error" :message="pageError ?? conversations.error ?? knowledgeBases.error ?? ''" />
      <p v-if="loading" class="chat-page__loading" role="status">正在加载会话…</p>
      <template v-else-if="conversation">
        <div v-if="visibleSyncError" class="chat-page__sync-error" role="alert">
          <span>回答已生成，但消息同步失败：{{ visibleSyncError }}</span>
          <button
            name="reload-messages"
            type="button"
            class="button button--secondary"
            :disabled="chat.syncingMessages"
            @click="reloadMessages"
          >重新加载消息</button>
        </div>
        <MessageList
          :conversation-id="conversation.id"
          :messages="messages"
          :optimistic-user="chat.optimisticUser"
          :draft-assistant="draftForConversation"
          :draft-citations="citationsForConversation"
          :phase="visiblePhase"
          :submission-baseline-message-ids="baselineForConversation"
          @citation="activeCitation = $event"
        />
        <div class="chat-page__composer">
          <AgentStatus :phase="visiblePhase" :status="visibleStatus" :error="visibleError" />
          <ChatComposer :active="activeStream" :can-retry="canRetry" @submit="send" @cancel="chat.cancel" @retry="retry" />
        </div>
      </template>
      <div v-else class="chat-page__empty">
        <h2>{{ knowledgeBases.selectedId ? '选择或创建会话' : '先选择知识库' }}</h2>
        <p>{{ knowledgeBases.selectedId ? '从会话历史继续对话，或创建一个新会话。' : '知识库是对话的全局上下文。' }}</p>
        <button v-if="knowledgeBases.selectedId" type="button" class="button" @click="startNewChat">创建会话</button>
        <RouterLink v-else class="button" :to="{ name: 'knowledge-bases' }">管理知识库</RouterLink>
      </div>
    </div>
  </ChatLayout>

  <ConversationCreateDialog :open="createOpen" :busy="creating" @create="create" @close="router.push({ name: 'chat' })" />
  <CitationDrawer :open="activeCitation !== null" :citation="activeCitation" @close="activeCitation = null" />
</template>

<style scoped>
.chat-page__sync-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin: 0 1rem;
  padding: 0.75rem 1rem;
  border: 1px solid color-mix(in srgb, var(--color-destructive), white 65%);
  border-radius: 0.5rem;
  color: var(--color-destructive);
  background: color-mix(in srgb, var(--color-destructive), white 94%);
}

.chat-page__route-error { display: grid; gap: 0.75rem; margin: 0 1rem; }
.chat-page__route-error-actions { display: flex; gap: 0.75rem; }

@media (max-width: 36rem) {
  .chat-page__sync-error { align-items: stretch; flex-direction: column; }
}
</style>
