<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <section class="empty-state">
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
    <slot />
  </section>
</template>

<style scoped>
.empty-state {
  display: grid;
  gap: 0.75rem;
  padding: 2.5rem 1.5rem;
  border: 1px dashed var(--color-border);
  border-radius: 0.75rem;
  text-align: center;
}

.empty-state h2,
.empty-state p {
  margin: 0;
}

.empty-state p {
  color: var(--color-text-muted);
}
</style>
