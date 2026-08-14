<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { CitationData } from '@/api/sse'
import type { MessageCitation } from '@/types/api'

const props = defineProps<{ open: boolean, citation: MessageCitation | CitationData | null }>()
const emit = defineEmits<{ close: [] }>()
const closeButton = ref<HTMLButtonElement | null>(null)
let previousFocus: HTMLElement | null = null

const filename = computed(() => {
  const metadata = props.citation && 'metadata' in props.citation ? props.citation.metadata : undefined
  return typeof metadata?.filename === 'string' && metadata.filename.trim() ? metadata.filename : '未知文件'
})

const score = computed(() => props.citation?.score === null || props.citation?.score === undefined
  ? null
  : `${(props.citation.score * 100).toFixed(1)}%`)

watch(() => props.open, async (open) => {
  if (open) {
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await nextTick()
    closeButton.value?.focus()
  } else {
    await nextTick()
    previousFocus?.focus()
  }
}, { immediate: true })

async function close(): Promise<void> {
  emit('close')
  await nextTick()
  previousFocus?.focus()
}

function keydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    void close()
  } else if (event.key === 'Tab') {
    event.preventDefault()
    closeButton.value?.focus()
  }
}
</script>

<template>
  <div v-if="open && citation" class="citation-drawer" role="presentation" @click.self="close">
    <section
      class="citation-drawer__panel"
      role="dialog"
      aria-modal="true"
      aria-labelledby="citation-drawer-title"
      @keydown="keydown"
    >
      <header class="citation-drawer__header">
        <div>
          <p class="citation-drawer__label">引用 {{ citation.source_label }}</p>
          <h2 id="citation-drawer-title">{{ filename }}</h2>
        </div>
        <button ref="closeButton" type="button" class="citation-drawer__close" aria-label="关闭引用详情" @click="close">×</button>
      </header>

      <dl class="citation-drawer__details">
        <template v-if="citation.section">
          <dt>章节</dt><dd>{{ citation.section }}</dd>
        </template>
        <template v-if="citation.page_number !== null">
          <dt>页码</dt><dd>第 {{ citation.page_number }} 页</dd>
        </template>
        <template v-if="score">
          <dt>相关度</dt><dd>{{ score }}</dd>
        </template>
        <dt>文档 ID</dt><dd>{{ citation.document_id }}</dd>
        <dt>片段 ID</dt><dd>{{ citation.chunk_id }}</dd>
      </dl>

      <div class="citation-drawer__quote">
        <h3>引用原文</h3>
        <blockquote>{{ citation.quote }}</blockquote>
      </div>
    </section>
  </div>
</template>

<style scoped>
.citation-drawer {
  position: fixed;
  z-index: 30;
  inset: 0;
  display: flex;
  justify-content: flex-end;
  background: rgb(23 26 43 / 38%);
}

.citation-drawer__panel {
  width: min(28rem, 100%);
  height: 100%;
  padding: 1.5rem;
  overflow-y: auto;
  background: var(--color-surface);
  box-shadow: -10px 0 32px rgb(23 26 43 / 14%);
}

.citation-drawer__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.citation-drawer__header h2,
.citation-drawer__label {
  margin: 0;
}

.citation-drawer__label {
  margin-bottom: 0.375rem;
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  font-weight: 700;
}

.citation-drawer__close {
  width: 2.5rem;
  height: 2.5rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: var(--color-text);
  background: var(--color-surface);
  font-size: 1.5rem;
}

.citation-drawer__details {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 0.625rem 1rem;
  margin: 1.5rem 0;
}

.citation-drawer__details dt {
  color: var(--color-text-muted);
}

.citation-drawer__details dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.citation-drawer__quote h3 {
  font-size: 1rem;
}

.citation-drawer__quote blockquote {
  margin: 0;
  padding: 1rem;
  border-left: 0.25rem solid var(--color-action);
  border-radius: 0 0.5rem 0.5rem 0;
  background: var(--color-page);
  line-height: 1.7;
  white-space: pre-wrap;
}

@media (max-width: 36rem) {
  .citation-drawer {
    align-items: flex-end;
  }

  .citation-drawer__panel {
    width: 100%;
    height: min(75vh, 42rem);
    border-radius: 1rem 1rem 0 0;
    box-shadow: 0 -10px 32px rgb(23 26 43 / 14%);
  }
}
</style>
