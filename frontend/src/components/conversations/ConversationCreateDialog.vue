<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ open: boolean, busy?: boolean }>()
const emit = defineEmits<{ create: [title: string], close: [] }>()
const title = ref('')
const error = ref<string | null>(null)

watch(() => props.open, (open) => {
  if (!open) {
    title.value = ''
    error.value = null
  }
})

function submit(): void {
  const trimmed = title.value.trim()
  if (!trimmed) {
    error.value = '会话标题不能为空'
    return
  }
  if (trimmed.length > 100) {
    error.value = '会话标题不能超过 100 个字符'
    return
  }
  error.value = null
  emit('create', trimmed)
}

function close(): void {
  emit('close')
}
</script>

<template>
  <div v-if="open" class="conversation-create-dialog" role="presentation">
    <section class="conversation-create-dialog__panel" role="dialog" aria-modal="true" aria-labelledby="conversation-create-title">
      <h2 id="conversation-create-title">创建会话</h2>
      <form @submit.prevent="submit">
        <label>
          会话标题
          <input v-model="title" :disabled="busy" maxlength="101" autocomplete="off">
        </label>
        <p v-if="error" role="alert">{{ error }}</p>
        <div class="conversation-create-dialog__actions">
          <button type="button" class="button button--secondary" :disabled="busy" @click="close">取消</button>
          <button type="submit" class="button" :disabled="busy">创建</button>
        </div>
      </form>
    </section>
  </div>
</template>

<style scoped>
.conversation-create-dialog { position: fixed; z-index: 10; inset: 0; display: grid; place-items: center; padding: 1rem; background: rgb(23 26 43 / 45%); }
.conversation-create-dialog__panel { width: min(100%, 28rem); padding: 1.5rem; border-radius: 0.75rem; background: var(--color-surface); box-shadow: var(--shadow-surface); }
.conversation-create-dialog__panel h2, .conversation-create-dialog__panel p { margin: 0; }
.conversation-create-dialog__panel form { display: grid; gap: 1rem; margin-top: 1rem; }
.conversation-create-dialog__panel label { display: grid; gap: 0.5rem; font-weight: 600; }
.conversation-create-dialog__panel input { width: 100%; padding: 0.625rem 0.75rem; border: 1px solid var(--color-border); border-radius: 0.5rem; }
.conversation-create-dialog__panel [role="alert"] { color: var(--color-destructive); }
.conversation-create-dialog__actions { display: flex; justify-content: flex-end; gap: 0.75rem; }
</style>
