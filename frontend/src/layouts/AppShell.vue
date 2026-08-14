<script setup lang="ts">
import { onMounted } from 'vue'
import AppSidebar from '@/components/navigation/AppSidebar.vue'
import { useKnowledgeBaseStore } from '@/stores/knowledge-bases'

const knowledgeBases = useKnowledgeBaseStore()

onMounted(() => knowledgeBases.load())
</script>

<template>
  <div class="app-shell">
    <AppSidebar :selected-knowledge-base-id="knowledgeBases.selectedId ?? undefined" />
    <main class="app-shell__content" tabindex="-1">
      <router-view />
    </main>
  </div>
</template>
