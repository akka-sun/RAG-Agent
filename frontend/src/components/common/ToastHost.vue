<script setup lang="ts">
import { useNotificationStore, type NotificationLevel } from '@/stores/notifications'

const notifications = useNotificationStore()

const labels: Record<NotificationLevel, string> = {
  info: '提示',
  success: '成功',
  warning: '注意',
  error: '错误',
}
</script>

<template>
  <div class="toast-host" aria-label="通知">
    <article
      v-for="notification in notifications.items"
      :key="notification.id"
      class="toast"
      :class="`toast--${notification.level}`"
      :role="notification.level === 'error' ? 'alert' : 'status'"
      :aria-live="notification.level === 'error' ? 'assertive' : 'polite'"
    >
      <p class="toast__message"><span class="toast__label">{{ labels[notification.level] }}：</span>{{ notification.message }}</p>
      <button
        class="toast__dismiss"
        type="button"
        :aria-label="`关闭通知：${notification.message}`"
        @click="notifications.dismiss(notification.id)"
      >
        关闭
      </button>
    </article>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  z-index: 1000;
  top: 1rem;
  right: 1rem;
  display: grid;
  gap: 0.75rem;
  width: min(24rem, calc(100vw - 2rem));
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 0.625rem;
  background: white;
  box-shadow: 0 0.5rem 1.5rem rgb(15 23 42 / 15%);
  pointer-events: auto;
}

.toast--error { border-color: color-mix(in srgb, var(--color-destructive), white 55%); }
.toast--warning { border-color: color-mix(in srgb, #b45309, white 55%); }
.toast--success { border-color: color-mix(in srgb, #15803d, white 55%); }
.toast__message { flex: 1; margin: 0; }
.toast__label { font-weight: 700; }
.toast__dismiss { border: 0; background: transparent; color: inherit; cursor: pointer; text-decoration: underline; }
</style>
