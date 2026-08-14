<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import DocumentPreview from '@/components/documents/DocumentPreview.vue'
import DocumentTable from '@/components/documents/DocumentTable.vue'
import DocumentUploader from '@/components/documents/DocumentUploader.vue'
import IngestionProgress from '@/components/documents/IngestionProgress.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import InlineAlert from '@/components/common/InlineAlert.vue'
import { useDocumentStore } from '@/stores/documents'

const route = useRoute()
const store = useDocumentStore()
const uploading = ref(false)
const selectedDocumentId = ref<string | null>(null)
const knowledgeBaseId = computed(() => String(route.params.knowledgeBaseId ?? ''))
const documents = computed(() => store.documentsByKnowledgeBase[knowledgeBaseId.value] ?? [])
const trackedTasks = computed(() => Object.values(store.tasks)
  .filter((task) => task.knowledgeBaseId === knowledgeBaseId.value))
const selectedDocument = computed(() => documents.value
  .find((document) => document.id === selectedDocumentId.value) ?? null)
let pageActive = true

async function load(): Promise<void> {
  const requestedKnowledgeBaseId = knowledgeBaseId.value
  if (!requestedKnowledgeBaseId) return
  try {
    await store.load(requestedKnowledgeBaseId)
  } catch {
    // The store exposes the backend error through the page alert.
  } finally {
    if (pageActive && knowledgeBaseId.value === requestedKnowledgeBaseId) {
      store.resumePolling(requestedKnowledgeBaseId)
    }
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
      <h1 id="knowledge-base-detail-title">文档</h1>
      <p class="page__description">上传文档，跟踪摄取进度，并安全查看原文与解析结果。</p>
    </header>

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
  </section>
</template>

<style scoped>
.knowledge-base-detail { display: grid; gap: 1.5rem; max-width: 78rem; }
.knowledge-base-detail__section { display: grid; gap: 1rem; padding: 1.25rem; border: 1px solid var(--color-border); border-radius: 0.75rem; }
.knowledge-base-detail__section h2, .knowledge-base-detail__section p { margin: 0; }
.knowledge-base-detail__section-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
</style>
