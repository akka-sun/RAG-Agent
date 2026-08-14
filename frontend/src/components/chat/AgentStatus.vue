<script setup lang="ts">
import { computed } from 'vue'
import type { ChatPhase } from '@/stores/chat'
const props = defineProps<{ phase: ChatPhase, status: string | null, error: string | null }>()

const label = computed(() => {
  if (props.phase === 'failed') return props.error ? `生成失败：${props.error}` : '生成失败，请重试'
  if (props.phase === 'cancelled') return '生成已停止'
  if (props.phase === 'retrieving') return '正在检索知识库'
  if (props.phase === 'sending') return '正在发送消息'
  if (props.phase === 'streaming' || props.status === 'running') return '助手正在生成回答'
  return ''
})
</script>

<template>
  <p
    v-if="label"
    class="agent-status"
    :class="`agent-status--${phase}`"
    :role="phase === 'failed' ? 'alert' : 'status'"
  >
    <span v-if="phase === 'sending' || phase === 'streaming' || phase === 'retrieving'" class="agent-status__pulse" aria-hidden="true" />
    {{ label }}
  </p>
</template>

<style scoped>
.agent-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.5rem 1rem;
  color: var(--color-text-muted);
  font-size: 0.8125rem;
}

.agent-status--failed { color: var(--color-destructive); }
.agent-status--cancelled { color: var(--color-warning); }

.agent-status__pulse {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 999px;
  background: var(--color-action);
}
</style>
