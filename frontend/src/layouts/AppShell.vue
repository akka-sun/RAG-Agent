<script setup lang="ts">
import AppSidebar from '@/components/navigation/AppSidebar.vue'
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="app-shell__content" tabindex="-1">
      <router-view />
    </main>
  </div>
</template>
