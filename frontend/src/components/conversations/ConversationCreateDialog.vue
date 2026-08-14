<script setup lang="ts">
import { ref, watch } from 'vue'
import ModalDialog from '@/components/common/ModalDialog.vue'

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
  if (trimmed.length > 200) {
    error.value = '会话标题不能超过 200 个字符'
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
  <ModalDialog
    class="conversation-create-dialog"
    :open="open"
    aria-labelledby="conversation-create-title"
    initial-focus="input[name='conversation-title']"
    @close="close"
  >
    <div class="conversation-create-dialog__content">
      <h2 id="conversation-create-title">创建会话</h2>
      <form @submit.prevent="submit">
        <label>
          会话标题
          <input v-model="title" name="conversation-title" :disabled="busy" maxlength="200" autocomplete="off">
        </label>
        <p v-if="error" role="alert">{{ error }}</p>
        <div class="conversation-create-dialog__actions">
          <button type="button" class="button button--secondary" :disabled="busy" @click="close">取消</button>
          <button type="submit" class="button" :disabled="busy">创建</button>
        </div>
      </form>
    </div>
  </ModalDialog>
</template>

<style scoped>
.conversation-create-dialog__content h2, .conversation-create-dialog__content p { margin: 0; }
.conversation-create-dialog__content form { display: grid; gap: 1rem; margin-top: 1rem; }
.conversation-create-dialog__content label { display: grid; gap: 0.5rem; font-weight: 600; }
.conversation-create-dialog__content input { width: 100%; padding: 0.625rem 0.75rem; border: 1px solid var(--color-border); border-radius: 0.5rem; }
.conversation-create-dialog__content [role="alert"] { color: var(--color-destructive); }
.conversation-create-dialog__actions { display: flex; justify-content: flex-end; gap: 0.75rem; }
</style>
