<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import InlineAlert from '@/components/common/InlineAlert.vue'
import KnowledgeBaseCard from '@/components/knowledge-base/KnowledgeBaseCard.vue'
import KnowledgeBaseForm from '@/components/knowledge-base/KnowledgeBaseForm.vue'
import { useKnowledgeBaseStore } from '@/stores/knowledge-bases'
import type { KnowledgeBaseCreate } from '@/types/api'

const router = useRouter()
const store = useKnowledgeBaseStore()
const creating = ref(false)
const deletingId = ref<string | null>(null)

async function create(input: KnowledgeBaseCreate): Promise<void> {
  creating.value = true
  try {
    const item = await store.create(input)
    await router.push({ name: 'knowledge-base-detail', params: { knowledgeBaseId: item.id } })
  } catch {
    // The store exposes its API error through the page alert.
  } finally {
    creating.value = false
  }
}

async function remove(): Promise<void> {
  if (!deletingId.value) return
  try {
    await store.remove(deletingId.value)
    deletingId.value = null
  } catch {
    // The store exposes its API error through the page alert.
  }
}
</script>

<template>
  <section class="page knowledge-bases-page" aria-labelledby="knowledge-bases-title">
    <p class="page__eyebrow">知识管理</p>
    <h1 id="knowledge-bases-title">知识库</h1>
    <p class="page__description">管理可供检索的知识库。</p>

    <div v-if="store.error" class="knowledge-bases-page__error">
      <InlineAlert :message="store.error" />
      <button type="button" class="button button--secondary" @click="store.load">重试加载</button>
    </div>

    <section class="knowledge-bases-page__create" aria-labelledby="create-knowledge-base-title">
      <h2 id="create-knowledge-base-title">创建知识库</h2>
      <KnowledgeBaseForm @submit="create" />
      <p v-if="creating" class="knowledge-bases-page__status" role="status">正在创建知识库…</p>
    </section>

    <p v-if="store.loading" class="knowledge-bases-page__status" role="status">正在加载知识库…</p>

    <template v-else>
      <EmptyState v-if="store.items.length === 0" title="还没有知识库" description="创建一个知识库后，即可上传并检索文档。" />
      <div v-else class="knowledge-bases-page__list" aria-label="知识库列表">
        <KnowledgeBaseCard
          v-for="knowledgeBase in store.items"
          :key="knowledgeBase.id"
          :knowledge-base="knowledgeBase"
          :selected="store.selectedId === knowledgeBase.id"
          @select="store.select"
          @remove="deletingId = $event"
        />
      </div>
    </template>
  </section>

  <ConfirmDialog :open="deletingId !== null" title="删除知识库" @confirm="remove" @cancel="deletingId = null" />
</template>

<style scoped>
.knowledge-bases-page { display: grid; gap: 1.5rem; }
.knowledge-bases-page__error { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 0.75rem; }
.knowledge-bases-page__create { display: grid; gap: 0.75rem; padding: 1.25rem; border-radius: 0.75rem; background: var(--color-page); }
.knowledge-bases-page__create h2, .knowledge-bases-page__status { margin: 0; }
.knowledge-bases-page__list { display: grid; gap: 1rem; }
.knowledge-bases-page__status { color: var(--color-text-muted); }

@media (max-width: 36rem) {
  .knowledge-bases-page__error { grid-template-columns: 1fr; }
}
</style>
