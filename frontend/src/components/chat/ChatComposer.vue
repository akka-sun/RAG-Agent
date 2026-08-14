<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{ active?: boolean, canRetry?: boolean, disabled?: boolean }>()
const emit = defineEmits<{ submit: [content: string, accept: () => void], cancel: [], retry: [] }>()
const content = ref('')
const sendDisabled = computed(() => props.active || props.disabled || content.value.trim().length === 0)

function submit(): void {
  if (sendDisabled.value) return
  const normalized = content.value.trim()
  emit('submit', normalized, () => { content.value = '' })
}

function keydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  submit()
}
</script>

<template>
  <form class="chat-composer" aria-label="发送消息" @submit.prevent="submit">
    <label class="chat-composer__label" for="chat-message">输入消息</label>
    <textarea
      id="chat-message"
      v-model="content"
      rows="3"
      :disabled="active || disabled"
      placeholder="基于当前知识库提问…"
      @keydown="keydown"
    />
    <div class="chat-composer__actions">
      <p class="chat-composer__hint">Enter 发送，Shift + Enter 换行</p>
      <button
        v-if="canRetry && !active"
        type="button"
        class="button button--secondary"
        aria-label="重试上一条消息"
        @click="$emit('retry')"
      >重试</button>
      <button
        v-if="active"
        type="button"
        class="button button--danger"
        aria-label="停止生成"
        @click="$emit('cancel')"
      >停止</button>
      <button type="submit" class="button" :disabled="sendDisabled">发送</button>
    </div>
  </form>
</template>

<style scoped>
.chat-composer {
  display: grid;
  gap: 0.625rem;
  padding: 0.875rem;
  border: 1px solid var(--color-border);
  border-radius: 0.875rem;
  background: var(--color-surface);
  box-shadow: var(--shadow-surface);
}

.chat-composer__label {
  position: absolute;
  overflow: hidden;
  width: 1px;
  height: 1px;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.chat-composer textarea {
  width: 100%;
  min-height: 4.75rem;
  padding: 0.5rem;
  resize: vertical;
  border: 0;
  color: var(--color-text);
  background: transparent;
  line-height: 1.5;
}

.chat-composer textarea:focus-visible {
  outline-offset: 0;
}

.chat-composer__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
}

.chat-composer__hint {
  margin: 0 auto 0 0;
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.chat-composer button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

@media (max-width: 36rem) {
  .chat-composer__hint {
    display: none;
  }
}
</style>
