<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { conversationsApi } from '@/api/resources'
import ConversationCreateDialog from '@/components/conversations/ConversationCreateDialog.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import InlineAlert from '@/components/common/InlineAlert.vue'
import { useConversationStore } from '@/stores/conversations'
import { useKnowledgeBaseStore } from '@/stores/knowledge-bases'

const route = useRoute()
const router = useRouter()
const conversations = useConversationStore()
const knowledgeBases = useKnowledgeBaseStore()
const pageError = ref<string | null>(null)
const loading = ref(false)
const creating = ref(false)
const createOpen = ref(false)
const conversation = ref<{ id: string, title: string } | null>(null)
const requestedConversationId = computed(() => typeof route.query.conversation === 'string' ? route.query.conversation : null)
const isNewFlow = computed(() => route.query.new === '1')
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
let routeGeneration = 0

async function resolveRoute(): Promise<void> {
  const generation = ++routeGeneration
  const isCurrent = () => generation === routeGeneration
  pageError.value = null
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
    pageError.value = '请选择已有会话，或创建一个新会话。'
    return
  }
  if (!uuidPattern.test(conversationId)) {
    conversations.select(null)
    pageError.value = '会话不存在或已失效，请返回会话列表重试。'
    return
  }

  loading.value = true
  try {
    const item = await conversationsApi.get(conversationId)
    if (!isCurrent()) return
    if (!item) throw new Error('会话不存在')
    knowledgeBases.select(item.knowledge_base_id)
    conversations.select(item.id)
    await conversations.loadMessages(item.id, isCurrent)
    if (!isCurrent()) return
    conversation.value = item
  } catch {
    if (!isCurrent()) return
    conversations.select(null)
    pageError.value = '会话不存在或已失效，请返回会话列表重试。'
  } finally {
    if (isCurrent()) loading.value = false
  }
}

async function create(title: string): Promise<void> {
  if (!knowledgeBases.selectedId) return
  creating.value = true
  try {
    const item = await conversations.create(knowledgeBases.selectedId, title)
    await router.replace({ name: 'chat', query: { conversation: item.id } })
  } catch {
    // The store exposes backend errors through the page alert.
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  if (knowledgeBases.items.length === 0 && !knowledgeBases.loading) await knowledgeBases.load()
  await resolveRoute()
})
watch(() => route.query, resolveRoute)
</script>

<template>
  <section class="page chat-page" aria-labelledby="chat-title">
    <p class="page__eyebrow">RAG Agent</p>
    <h1 id="chat-title">{{ conversation?.title ?? (isNewFlow ? '创建会话' : '会话') }}</h1>
    <p class="page__description">基于已选知识库查看已持久化的对话消息。</p>

    <InlineAlert v-if="pageError || conversations.error" :message="pageError ?? conversations.error ?? ''" />
    <p v-if="loading" role="status">正在加载会话…</p>
    <div v-else-if="conversation" class="chat-page__messages" aria-label="消息记录">
      <article v-for="message in conversations.messagesByConversation[conversation.id] ?? []" :key="message.id">
        <strong>{{ message.role === 'user' ? '你' : '助手' }}</strong>
        <p>{{ message.content }}</p>
      </article>
      <EmptyState
        v-if="conversations.messagesByConversation[conversation.id]?.length === 0"
        title="还没有消息"
        description="该会话尚未保存任何消息。"
      />
    </div>
    <RouterLink v-if="pageError" class="button button--secondary" :to="{ name: 'conversations' }">返回会话列表</RouterLink>
  </section>

  <ConversationCreateDialog :open="createOpen" :busy="creating" @create="create" @close="router.push({ name: 'conversations' })" />
</template>

<style scoped>
.chat-page { display: grid; gap: 1.5rem; }
.chat-page__messages { display: grid; gap: 0.75rem; }
.chat-page__messages article { padding: 1rem; border: 1px solid var(--color-border); border-radius: 0.75rem; }
.chat-page__messages strong, .chat-page__messages p { margin: 0; }
.chat-page__messages p { margin-top: 0.5rem; white-space: pre-wrap; }
</style>
