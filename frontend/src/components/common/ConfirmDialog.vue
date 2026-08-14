<script setup lang="ts">
import ModalDialog from './ModalDialog.vue'

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
  <ModalDialog :open="open" :aria-label="title" @close="$emit('cancel')">
    <div class="confirm-dialog__content">
      <h2>{{ title }}</h2>
      <p>删除后，关联的文档、会话和索引也会被移除，且无法恢复。</p>
      <div class="confirm-dialog__actions">
        <button type="button" class="button button--secondary" @click="$emit('cancel')">取消</button>
        <button type="button" class="button button--danger" @click="$emit('confirm')">{{ confirmLabel }}</button>
      </div>
    </div>
  </ModalDialog>
</template>

<style scoped>
.confirm-dialog__content h2,
.confirm-dialog__content p {
  margin: 0;
}

.confirm-dialog__content p {
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
