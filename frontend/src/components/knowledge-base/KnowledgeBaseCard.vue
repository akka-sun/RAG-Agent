<script setup lang="ts">
import type { KnowledgeBase } from '@/types/api'

defineProps<{
  knowledgeBase: KnowledgeBase
  selected?: boolean
  documentCount?: number
}>()

defineEmits<{
  select: [id: string]
  remove: [id: string]
}>()

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
</script>

<template>
  <article class="knowledge-base-card" :class="{ 'knowledge-base-card--selected': selected }">
    <div class="knowledge-base-card__heading">
      <h2>{{ knowledgeBase.name }}</h2>
      <button type="button" class="button button--secondary" @click="$emit('select', knowledgeBase.id)">
        {{ selected ? '当前知识库' : '设为当前' }}
      </button>
    </div>
    <p v-if="knowledgeBase.description" class="knowledge-base-card__description">{{ knowledgeBase.description }}</p>
    <dl class="knowledge-base-card__details">
      <div><dt>嵌入模型</dt><dd>{{ knowledgeBase.embedding_model }}</dd></div>
      <div><dt>向量维度</dt><dd>{{ knowledgeBase.embedding_dimension }}</dd></div>
      <div v-if="documentCount !== undefined"><dt>文档数量</dt><dd>{{ documentCount }}</dd></div>
      <div><dt>创建时间</dt><dd>{{ formatDate(knowledgeBase.created_at) }}</dd></div>
      <div><dt>更新时间</dt><dd>{{ formatDate(knowledgeBase.updated_at) }}</dd></div>
    </dl>
    <div class="knowledge-base-card__actions">
      <RouterLink class="button button--secondary" :to="{ name: 'knowledge-base-detail', params: { knowledgeBaseId: knowledgeBase.id } }">查看详情</RouterLink>
      <button type="button" class="button button--danger" @click="$emit('remove', knowledgeBase.id)">删除</button>
    </div>
  </article>
</template>

<style scoped>
.knowledge-base-card { padding: 1.25rem; border: 1px solid var(--color-border); border-radius: 0.75rem; background: var(--color-surface); }
.knowledge-base-card--selected { border-color: var(--color-action); }
.knowledge-base-card__heading, .knowledge-base-card__actions { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; }
.knowledge-base-card h2, .knowledge-base-card__description { margin: 0; }
.knowledge-base-card__description { margin-top: 0.75rem; color: var(--color-text-muted); }
.knowledge-base-card__details { display: grid; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr)); gap: 0.75rem 1.5rem; margin: 1rem 0; }
.knowledge-base-card__details div { display: grid; gap: 0.25rem; }
.knowledge-base-card__details dt { color: var(--color-text-muted); font-size: 0.8125rem; }
.knowledge-base-card__details dd { margin: 0; }
.knowledge-base-card__actions { justify-content: flex-end; }
</style>
