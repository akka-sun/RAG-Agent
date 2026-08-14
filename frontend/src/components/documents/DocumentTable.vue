<script setup lang="ts">
import { ref } from 'vue'
import type { DocumentRecord } from '@/types/api'

defineProps<{ documents: DocumentRecord[] }>()

const emit = defineEmits<{
  preview: [documentId: string]
  retry: [documentId: string]
  remove: [documentId: string]
}>()

const pendingDelete = ref<DocumentRecord | null>(null)

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function confirmRemove(): void {
  if (!pendingDelete.value) return
  emit('remove', pendingDelete.value.id)
  pendingDelete.value = null
}
</script>

<template>
  <div class="document-table-wrap">
    <table class="document-table">
      <thead>
        <tr>
          <th scope="col">文件名</th>
          <th scope="col">解析器</th>
          <th scope="col">大小</th>
          <th scope="col">状态</th>
          <th scope="col">分块数</th>
          <th scope="col">更新时间</th>
          <th scope="col">后端错误</th>
          <th scope="col">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="document in documents" :key="document.id">
          <td>{{ document.filename }}</td>
          <td>{{ document.parser_name }}</td>
          <td>{{ formatBytes(document.size_bytes) }}</td>
          <td><span class="document-table__status" :data-status="document.status">{{ document.status }}</span></td>
          <td>{{ document.chunk_count }}</td>
          <td>{{ formatDate(document.updated_at) }}</td>
          <td class="document-table__error">{{ document.error ?? '—' }}</td>
          <td>
            <div class="document-table__actions">
              <button type="button" class="button button--secondary" @click="$emit('preview', document.id)">预览与下载</button>
              <button v-if="document.status === 'failed'" name="retry-document" type="button" class="button button--secondary" @click="$emit('retry', document.id)">重试</button>
              <button
                name="remove-document"
                type="button"
                class="button button--danger"
                :disabled="document.status === 'pending' || document.status === 'processing'"
                :title="document.status === 'pending' || document.status === 'processing' ? '摄取完成后才能删除' : undefined"
                @click="pendingDelete = document"
              >删除</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <div v-if="pendingDelete" class="document-table__confirm" role="presentation">
    <section role="dialog" aria-modal="true" :aria-label="`确认删除 ${pendingDelete.filename}`">
      <h2>确认删除 {{ pendingDelete.filename }}</h2>
      <p>文档原文、解析结果和索引将被删除，且无法恢复。</p>
      <div class="document-table__confirm-actions">
        <button type="button" class="button button--secondary" @click="pendingDelete = null">取消</button>
        <button name="confirm-remove-document" type="button" class="button button--danger" @click="confirmRemove">确认删除</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.document-table-wrap { overflow-x: auto; }
.document-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.document-table th, .document-table td { padding: 0.75rem; border-bottom: 1px solid var(--color-border); text-align: left; vertical-align: top; }
.document-table th { color: var(--color-text-muted); font-size: 0.8125rem; white-space: nowrap; }
.document-table__status { font-weight: 600; }
.document-table__status[data-status="completed"] { color: var(--color-success); }
.document-table__status[data-status="failed"], .document-table__error { color: var(--color-destructive); }
.document-table__actions { display: flex; flex-wrap: wrap; gap: 0.5rem; min-width: 18rem; }
.document-table__actions .button { min-height: 2rem; padding: 0.25rem 0.625rem; }
.document-table__confirm { position: fixed; z-index: 10; inset: 0; display: grid; place-items: center; padding: 1rem; background: rgb(23 26 43 / 45%); }
.document-table__confirm section { width: min(100%, 28rem); padding: 1.5rem; border-radius: 0.75rem; background: var(--color-surface); box-shadow: var(--shadow-surface); }
.document-table__confirm h2, .document-table__confirm p { margin: 0; }
.document-table__confirm p { margin-top: 0.75rem; color: var(--color-text-muted); }
.document-table__confirm-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.5rem; }
</style>
