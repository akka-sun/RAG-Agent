<script setup lang="ts">
import type { KnowledgeBase } from '@/types/api'

defineProps<{
  title: string
  knowledgeBases: KnowledgeBase[]
  selectedKnowledgeBaseId: string | null
}>()
defineEmits<{ selectKnowledgeBase: [id: string], toggleRail: [], newChat: [] }>()
</script>

<template>
  <header class="chat-header">
    <button type="button" class="chat-header__rail-toggle" aria-label="打开会话历史" @click="$emit('toggleRail')">☰</button>
    <div class="chat-header__title">
      <p>当前会话</p>
      <h1>{{ title }}</h1>
    </div>
    <label class="chat-header__knowledge-base">
      <span>知识库</span>
      <select
        aria-label="当前知识库"
        :value="selectedKnowledgeBaseId ?? ''"
        @change="$emit('selectKnowledgeBase', ($event.target as HTMLSelectElement).value)"
      >
        <option value="" disabled>选择知识库</option>
        <option v-for="knowledgeBase in knowledgeBases" :key="knowledgeBase.id" :value="knowledgeBase.id">{{ knowledgeBase.name }}</option>
      </select>
    </label>
    <button type="button" class="button chat-header__new" @click="$emit('newChat')">新对话</button>
  </header>
</template>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-height: 4.5rem;
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.chat-header__rail-toggle {
  display: none;
  width: 2.5rem;
  height: 2.5rem;
  border: 1px solid var(--color-border);
  border-radius: 0.5rem;
  background: var(--color-surface);
}

.chat-header__title { min-width: 0; }
.chat-header__title p,
.chat-header__title h1 { margin: 0; }
.chat-header__title p { color: var(--color-text-muted); font-size: 0.75rem; }
.chat-header__title h1 { overflow: hidden; font-size: 1.125rem; text-overflow: ellipsis; white-space: nowrap; }
.chat-header__knowledge-base { display: grid; gap: 0.25rem; margin-left: auto; color: var(--color-text-muted); font-size: 0.75rem; }
.chat-header__knowledge-base select { min-width: 10rem; padding: 0.5rem; border: 1px solid var(--color-border); border-radius: 0.5rem; background: var(--color-surface); }

@media (max-width: 64rem) {
  .chat-header__rail-toggle { display: inline-grid; place-items: center; }
}

@media (max-width: 36rem) {
  .chat-header { flex-wrap: wrap; padding: 0.75rem; }
  .chat-header__title { flex: 1; }
  .chat-header__knowledge-base { order: 4; width: 100%; margin: 0; }
  .chat-header__knowledge-base select { width: 100%; }
  .chat-header__new { padding-inline: 0.625rem; }
}
</style>
