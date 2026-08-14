<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppSidebar from '@/components/navigation/AppSidebar.vue'
import { useKnowledgeBaseStore } from '@/stores/knowledge-bases'

const knowledgeBases = useKnowledgeBaseStore()
const navOpen = ref(false)

onMounted(() => knowledgeBases.load())
</script>

<template>
  <div class="app-shell" @keydown.esc="navOpen = false">
    <button
      type="button"
      class="app-shell__nav-toggle"
      aria-controls="global-navigation"
      :aria-expanded="navOpen"
      aria-label="打开主导航"
      @click="navOpen = !navOpen"
    >☰</button>
    <button v-if="navOpen" type="button" class="app-shell__nav-backdrop" aria-label="关闭主导航" @click="navOpen = false" />
    <AppSidebar
      id="global-navigation"
      :class="{ 'app-sidebar--open': navOpen }"
      :selected-knowledge-base-id="knowledgeBases.selectedId ?? undefined"
      @click="navOpen = false"
    />
    <main class="app-shell__content" tabindex="-1">
      <router-view />
    </main>
  </div>
</template>
