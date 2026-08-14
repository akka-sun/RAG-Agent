<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ConversationCreateDialog from '@/components/conversations/ConversationCreateDialog.vue'
import ConversationList from '@/components/conversations/ConversationList.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import InlineAlert from '@/components/common/InlineAlert.vue'
import { useConversationStore } from '@/stores/conversations'
import { useKnowledgeBaseStore } from '@/stores/knowledge-bases'

const router = useRouter()
const conversations = useConversationStore()
const knowledgeBases = useKnowledgeBaseStore()
const creating = ref(false)
const createOpen = ref(false)
const deletingId = ref<string | null>(null)
const selectedKnowledgeBaseId = computed({
  get: () => knowledgeBases.selectedId ?? '',
  set: (id: string) => knowledgeBases.select(id || null),
})
const items = computed(() => selectedKnowledgeBaseId.value
  ? conversations.itemsByKnowledgeBase[selectedKnowledgeBaseId.value] ?? []
  : [])

async function load(): Promise<void> {
  if (!selectedKnowledgeBaseId.value) return
  try {
    await conversations.loadForKnowledgeBase(selectedKnowledgeBaseId.value)
  } catch {
    // The store exposes backend errors through the page alert.
  }
}

async function create(title: string): Promise<void> {
  if (!selectedKnowledgeBaseId.value) return
  creating.value = true
  try {
    const conversation = await conversations.create(selectedKnowledgeBaseId.value, title)
    createOpen.value = false
    await router.push({ name: 'chat', query: { conversation: conversation.id } })
  } catch {
    // The store exposes backend errors through the page alert.
  } finally {
    creating.value = false
  }
}

async function remove(): Promise<void> {
  if (!deletingId.value) return
  try {
    await conversations.remove(deletingId.value)
    deletingId.value = null
  } catch {
    // The store exposes backend errors through the page alert.
  }
}

async function enter(conversationId: string): Promise<void> {
  conversations.select(conversationId)
  await router.push({ name: 'chat', query: { conversation: conversationId } })
}

onMounted(async () => {
  if (knowledgeBases.items.length === 0 && !knowledgeBases.loading) await knowledgeBases.load()
  await load()
})
watch(selectedKnowledgeBaseId, load)
</script>

<template>
  <section class="page conversations-page" aria-labelledby="conversations-title">
    <header>
      <p class="page__eyebrow">对话管理</p>
      <h1 id="conversations-title">会话</h1>
      <p class="page__description">浏览和继续已有会话。</p>
    </header>

    <InlineAlert v-if="conversations.error" :message="conversations.error" />

    <label v-if="knowledgeBases.items.length" class="conversations-page__knowledge-base">
      知识库
      <select v-model="selectedKnowledgeBaseId">
        <option v-for="knowledgeBase in knowledgeBases.items" :key="knowledgeBase.id" :value="knowledgeBase.id">{{ knowledgeBase.name }}</option>
      </select>
    </label>

    <EmptyState
      v-if="!knowledgeBases.loading && knowledgeBases.items.length === 0"
      title="请先创建知识库"
      description="创建知识库并上传资料后，即可在这里管理会话。"
    />

    <template v-else-if="selectedKnowledgeBaseId">
      <div class="conversations-page__heading">
        <h2>会话列表</h2>
        <button type="button" class="button" @click="createOpen = true">创建会话</button>
      </div>
      <p v-if="conversations.loading" role="status">正在加载会话…</p>
      <EmptyState v-else-if="items.length === 0" title="还没有会话" description="创建一个会话，开始基于当前知识库提问。" />
      <ConversationList
        v-else
        :conversations="items"
        :messages-by-conversation="conversations.messagesByConversation"
        @enter="enter"
        @remove="deletingId = $event"
      />
    </template>
  </section>

  <ConversationCreateDialog :open="createOpen" :busy="creating" @create="create" @close="createOpen = false" />
  <div v-if="deletingId" class="conversations-page__confirm" role="presentation">
    <section role="dialog" aria-modal="true" aria-label="删除会话">
      <h2>删除会话</h2>
      <p>删除后将无法恢复该会话及其消息。</p>
      <div>
        <button type="button" class="button button--secondary" @click="deletingId = null">取消</button>
        <button type="button" class="button button--danger" @click="remove">删除</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.conversations-page { display: grid; gap: 1.5rem; }
.conversations-page__knowledge-base { display: grid; gap: 0.5rem; max-width: 24rem; font-weight: 600; }
.conversations-page__knowledge-base select { padding: 0.625rem 0.75rem; border: 1px solid var(--color-border); border-radius: 0.5rem; background: var(--color-surface); }
.conversations-page__heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.conversations-page__heading h2, .conversations-page__confirm h2, .conversations-page__confirm p { margin: 0; }
.conversations-page__confirm { position: fixed; z-index: 10; inset: 0; display: grid; place-items: center; padding: 1rem; background: rgb(23 26 43 / 45%); }
.conversations-page__confirm section { display: grid; gap: 1rem; width: min(100%, 28rem); padding: 1.5rem; border-radius: 0.75rem; background: var(--color-surface); box-shadow: var(--shadow-surface); }
.conversations-page__confirm section > div { display: flex; justify-content: flex-end; gap: 0.75rem; }
</style>
