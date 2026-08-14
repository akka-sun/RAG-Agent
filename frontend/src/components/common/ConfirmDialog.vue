<script setup lang="ts">
withDefaults(defineProps<{
  open: boolean
  title: string
  confirmLabel?: string
}>(), {
  confirmLabel: '确认删除',
})

defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <div v-if="open" class="confirm-dialog" role="presentation">
    <section class="confirm-dialog__panel" role="dialog" aria-modal="true" :aria-label="title">
      <h2>{{ title }}</h2>
      <p>删除后，关联的文档、会话和索引也会被移除，且无法恢复。</p>
      <div class="confirm-dialog__actions">
        <button type="button" class="button button--secondary" @click="$emit('cancel')">取消</button>
        <button type="button" class="button button--danger" @click="$emit('confirm')">{{ confirmLabel }}</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.confirm-dialog {
  position: fixed;
  z-index: 10;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgb(23 26 43 / 45%);
}

.confirm-dialog__panel {
  width: min(100%, 28rem);
  padding: 1.5rem;
  border-radius: 0.75rem;
  background: var(--color-surface);
  box-shadow: var(--shadow-surface);
}

.confirm-dialog__panel h2,
.confirm-dialog__panel p {
  margin: 0;
}

.confirm-dialog__panel p {
  margin-top: 0.75rem;
  color: var(--color-text-muted);
}

.confirm-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
</style>
