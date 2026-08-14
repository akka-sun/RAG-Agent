<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps<{
  selectedKnowledgeBaseId?: string
}>()

const route = useRoute()
const selectedKnowledgeBaseId = computed(() => props.selectedKnowledgeBaseId ?? route.params.knowledgeBaseId)
const documentsTarget = computed(() => {
  if (typeof selectedKnowledgeBaseId.value === 'string' && selectedKnowledgeBaseId.value.length > 0) {
    return { name: 'knowledge-base-detail', params: { knowledgeBaseId: selectedKnowledgeBaseId.value } }
  }

  return { name: 'knowledge-bases' }
})
</script>

<template>
  <aside class="app-sidebar" aria-label="主导航">
    <div class="app-sidebar__brand">RAG Agent</div>
    <nav class="app-sidebar__nav" aria-label="产品区域">
      <RouterLink class="app-sidebar__link" :to="{ name: 'chat', query: { new: '1' } }">
        <span class="app-sidebar__label">新对话</span>
      </RouterLink>
      <RouterLink class="app-sidebar__link" :to="{ name: 'conversations' }">
        <span class="app-sidebar__label">会话</span>
      </RouterLink>
      <RouterLink class="app-sidebar__link" :to="{ name: 'knowledge-bases' }">
        <span class="app-sidebar__label">知识库</span>
      </RouterLink>
      <RouterLink class="app-sidebar__link" :to="documentsTarget">
        <span class="app-sidebar__label">文档</span>
      </RouterLink>
      <RouterLink class="app-sidebar__link" :to="{ name: 'status' }">
        <span class="app-sidebar__label">系统状态</span>
      </RouterLink>
    </nav>
  </aside>
</template>
