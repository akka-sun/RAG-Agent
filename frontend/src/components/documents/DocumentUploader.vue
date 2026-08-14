<script lang="ts">
const MAX_UPLOAD_SIZE = 5 * 1024 * 1024
const SUPPORTED_EXTENSIONS = ['.md', '.txt', '.pdf']

export function validateUpload(file: File): string | null {
  if (file.size === 0) return '文件不能为空'
  if (file.size > MAX_UPLOAD_SIZE) return '文件不能超过 5 MiB'
  const filename = file.name.toLowerCase()
  if (!SUPPORTED_EXTENSIONS.some((extension) => filename.endsWith(extension))) {
    return '仅支持 .md、.txt 和 .pdf'
  }
  return null
}
</script>

<script setup lang="ts">
import { computed, ref } from 'vue'

defineProps<{ busy?: boolean }>()

const emit = defineEmits<{
  upload: [file: File, parser: 'mineru' | 'paddlex' | undefined]
}>()

const selectedFile = ref<File | null>(null)
const parser = ref<'' | 'mineru' | 'paddlex'>('')
const error = ref('')
const isPdf = computed(() => selectedFile.value?.name.toLowerCase().endsWith('.pdf') ?? false)

function selectFile(event: Event): void {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
  parser.value = ''
  error.value = selectedFile.value ? validateUpload(selectedFile.value) ?? '' : '请选择文件'
}

function submit(): void {
  if (!selectedFile.value) {
    error.value = '请选择文件'
    return
  }
  error.value = validateUpload(selectedFile.value) ?? ''
  if (error.value) return
  if (isPdf.value && !parser.value) {
    error.value = '请选择 PDF 解析器'
    return
  }
  emit('upload', selectedFile.value, isPdf.value ? parser.value || undefined : undefined)
}
</script>

<template>
  <form class="document-uploader" novalidate @submit.prevent="submit">
    <div class="document-uploader__field">
      <label for="document-file">选择文档</label>
      <input
        id="document-file"
        type="file"
        accept=".md,.txt,.pdf"
        :disabled="busy"
        @change="selectFile"
      >
      <p class="document-uploader__hint">支持 Markdown、文本和 PDF，单个文件不超过 5 MiB。</p>
    </div>

    <div v-if="isPdf" class="document-uploader__field">
      <label for="document-parser">PDF 解析器</label>
      <select id="document-parser" v-model="parser" name="parser" :disabled="busy" required>
        <option value="" disabled>请选择解析器</option>
        <option value="mineru">MinerU</option>
        <option value="paddlex">PaddleX</option>
      </select>
    </div>

    <p v-if="error" class="document-uploader__error" role="alert">{{ error }}</p>
    <button type="submit" class="button" :disabled="busy">{{ busy ? '正在上传…' : '上传文档' }}</button>
  </form>
</template>

<style scoped>
.document-uploader { display: grid; grid-template-columns: minmax(0, 1fr) minmax(10rem, 14rem) auto; align-items: end; gap: 1rem; }
.document-uploader__field { display: grid; gap: 0.5rem; }
.document-uploader input, .document-uploader select { width: 100%; min-height: 2.5rem; padding: 0.5rem 0.75rem; border: 1px solid var(--color-border); border-radius: 0.5rem; color: var(--color-text); background: var(--color-surface); }
.document-uploader__hint, .document-uploader__error { grid-column: 1 / -1; margin: 0; font-size: 0.875rem; }
.document-uploader__hint { color: var(--color-text-muted); }
.document-uploader__error { color: var(--color-destructive); }

@media (max-width: 44rem) {
  .document-uploader { grid-template-columns: 1fr; }
}
</style>
