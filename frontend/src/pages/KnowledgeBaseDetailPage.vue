<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError } from '@/api/client'
import { knowledgeBasesApi } from '@/api/resources'
import DocumentPreview from '@/components/documents/DocumentPreview.vue'
import DocumentTable from '@/components/documents/DocumentTable.vue'
import DocumentUploader from '@/components/documents/DocumentUploader.vue'
import IngestionProgress from '@/components/documents/IngestionProgress.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import InlineAlert from '@/components/common/InlineAlert.vue'
import { useDocumentStore } from '@/stores/documents'
import type { KnowledgeBase } from '@/types/api'

const route = useRoute()
const store = useDocumentStore()
const uploading = ref(false)
const loadingKnowledgeBase = ref(false)
const knowledgeBase = ref<KnowledgeBase | null>(null)
const knowledgeBaseError = ref<string | null>(null)
const knowledgeBaseNotFound = ref(false)
const selectedDocumentId = ref<string | null>(null)
const knowledgeBaseId = computed(() => String(route.params.knowledgeBaseId ?? ''))
const documents = computed(() => store.documentsByKnowledgeBase[knowledgeBaseId.value] ?? [])
const trackedTasks = computed(() => Object.values(store.tasks)
  .filter((task) => task.knowledgeBaseId === knowledgeBaseId.value))
const selectedDocument = computed(() => documents.value
  .find((document) => document.id === selectedDocumentId.value) ?? null)
let pageActive = true
let loadGeneration = 0

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '知识库加载失败，请稍后重试。'
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

async function load(): Promise<void> {
  const requestedKnowledgeBaseId = knowledgeBaseId.value
  if (!requestedKnowledgeBaseId) return
  const generation = ++loadGeneration
  const isCurrent = () => pageActive
    && generation === loadGeneration
    && knowledgeBaseId.value === requestedKnowledgeBaseId
  loadingKnowledgeBase.value = true
  knowledgeBase.value = null
  knowledgeBaseError.value = null
  knowledgeBaseNotFound.value = false

  try {
    const item = await knowledgeBasesApi.get(requestedKnowledgeBaseId)
    if (!isCurrent()) return
    if (!item) throw new Error('知识库接口返回了空数据。')
    knowledgeBase.value = item
  } catch (reason) {
    if (!isCurrent()) return
    knowledgeBaseNotFound.value = reason instanceof ApiError && reason.status === 404
    if (!knowledgeBaseNotFound.value) knowledgeBaseError.value = errorMessage(reason)
    return
  } finally {
    if (isCurrent()) loadingKnowledgeBase.value = false
  }

  try {
    await store.load(requestedKnowledgeBaseId)
  } catch {
    // The document store exposes its backend error through the page alert.
  } finally {
    if (isCurrent()) store.resumePolling(requestedKnowledgeBaseId)
  }
}

async function upload(file: File, parser: 'mineru' | 'paddlex' | undefined): Promise<void> {
  uploading.value = true
  try {
    await store.upload(knowledgeBaseId.value, file, parser)
  } catch {
    // The store exposes the backend error through the page alert.
  } finally {
    uploading.value = false
  }
}

async function retry(documentId: string): Promise<void> {
  try {
    await store.retry(knowledgeBaseId.value, documentId)
  } catch {
    // The store exposes the backend error through the page alert.
  }
}

async function remove(documentId: string): Promise<void> {
  try {
    await store.remove(knowledgeBaseId.value, documentId)
    if (selectedDocumentId.value === documentId) selectedDocumentId.value = null
  } catch {
    // The store exposes the backend error through the page alert.
  }
}

onMounted(load)
watch(knowledgeBaseId, async (next, previous) => {
  if (next === previous) return
  loadGeneration += 1
  store.stopAllPolling()
  selectedDocumentId.value = null
  await load()
})
onBeforeUnmount(() => {
  pageActive = false
  store.stopAllPolling()
})
</script>

<template>
  <section class="page knowledge-base-detail" aria-labelledby="knowledge-base-detail-title">
    <header>
      <p class="page__eyebrow">知识管理</p>
      <h1 id="knowledge-base-detail-title">{{ knowledgeBase?.name ?? '知识库详情' }}</h1>
      <p v-if="knowledgeBase" class="page__description">{{ knowledgeBase.description || '暂无描述' }}</p>
    </header>

    <p v-if="loadingKnowledgeBase" role="status">正在加载知识库…</p>

    <EmptyState
      v-else-if="knowledgeBaseNotFound"
      title="知识库不存在或已被删除"
      description="请返回知识库列表，选择仍然可用的知识库。"
    >
      <RouterLink class="button" :to="{ name: 'knowledge-bases' }">返回知识库列表</RouterLink>
    </EmptyState>

    <div v-else-if="knowledgeBaseError" class="knowledge-base-detail__load-error">
      <InlineAlert :message="knowledgeBaseError" />
      <button name="retry-knowledge-base" type="button" class="button button--secondary" @click="load">重试</button>
    </div>

    <template v-else-if="knowledgeBase">
      <dl class="knowledge-base-detail__metadata">
        <div><dt>嵌入模型</dt><dd>{{ knowledgeBase.embedding_model }}</dd></div>
        <div><dt>向量维度</dt><dd>{{ knowledgeBase.embedding_dimension }}</dd></div>
        <div><dt>创建时间</dt><dd>{{ formatDate(knowledgeBase.created_at) }}</dd></div>
        <div><dt>更新时间</dt><dd>{{ formatDate(knowledgeBase.updated_at) }}</dd></div>
      </dl>

      <InlineAlert v-if="store.error" :message="store.error" />

      <section class="knowledge-base-detail__section" aria-labelledby="upload-document-title">
        <h2 id="upload-document-title">上传文档</h2>
        <DocumentUploader :busy="uploading" @upload="upload" />
      </section>

      <IngestionProgress :tasks="trackedTasks" />

      <section class="knowledge-base-detail__section" aria-labelledby="document-list-title">
        <div class="knowledge-base-detail__section-heading">
          <h2 id="document-list-title">文档列表</h2>
          <button type="button" class="button button--secondary" :disabled="store.loading" @click="load">刷新</button>
        </div>
        <p v-if="store.loading" role="status">正在加载文档…</p>
        <EmptyState v-else-if="documents.length === 0" title="还没有文档" description="上传 .md、.txt 或 .pdf 文件开始构建知识库。" />
        <DocumentTable v-else :documents="documents" @preview="selectedDocumentId = $event" @retry="retry" @remove="remove" />
      </section>

      <DocumentPreview v-if="selectedDocument" :knowledge-base-id="knowledgeBaseId" :document="selectedDocument" />
    </template>
  </section>
</template>

<style scoped>
.knowledge-base-detail { display: grid; gap: 1.5rem; max-width: 78rem; }
.knowledge-base-detail__load-error { display: flex; align-items: center; gap: 0.75rem; }
.knowledge-base-detail__metadata { display: grid; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr)); gap: 0.75rem 1.5rem; margin: 0; padding: 1.25rem; border: 1px solid var(--color-border); border-radius: 0.75rem; }
.knowledge-base-detail__metadata div { display: grid; gap: 0.25rem; }
.knowledge-base-detail__metadata dt { color: var(--color-text-muted); font-size: 0.8125rem; }
.knowledge-base-detail__metadata dd { margin: 0; }
.knowledge-base-detail__section { display: grid; gap: 1rem; padding: 1.25rem; border: 1px solid var(--color-border); border-radius: 0.75rem; }
.knowledge-base-detail__section h2, .knowledge-base-detail__section p { margin: 0; }
.knowledge-base-detail__section-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
</style>
