<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template>
  <p class="inline-alert" role="alert">{{ message }}</p>
</template>

<style scoped>
.inline-alert {
  margin: 0;
  padding: 0.75rem 1rem;
  border: 1px solid color-mix(in srgb, var(--color-destructive), white 65%);
  border-radius: 0.5rem;
  color: var(--color-destructive);
  background: color-mix(in srgb, var(--color-destructive), white 94%);
}
</style>
