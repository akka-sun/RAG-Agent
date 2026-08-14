<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { documentsApi } from '@/api/resources'
import type { BlobResponse } from '@/api/client'
import type { DocumentRecord } from '@/types/api'

const props = defineProps<{
  knowledgeBaseId: string
  document: DocumentRecord
}>()

type PreviewMode = 'none' | 'text' | 'pdf'

const loading = ref(false)
const error = ref('')
const mode = ref<PreviewMode>('none')
const text = ref('')
const previewUrl = ref<string | null>(null)
const assetIndexes = ref<number[]>([])
const assetUrls = ref<Record<number, string>>({})
let generation = 0
let previewController: AbortController | null = null
const assetControllers = new Map<number, AbortController>()
const downloadControllers = new Set<AbortController>()

function messageFor(reason: unknown): string {
  return reason instanceof Error ? reason.message : '预览加载失败，请稍后重试。'
}

function revoke(url: string | null): void {
  if (url) URL.revokeObjectURL(url)
}

function resetPreview(): void {
  generation += 1
  previewController?.abort()
  previewController = null
  for (const controller of assetControllers.values()) controller.abort()
  assetControllers.clear()
  for (const controller of downloadControllers) controller.abort()
  downloadControllers.clear()
  revoke(previewUrl.value)
  previewUrl.value = null
  for (const url of Object.values(assetUrls.value)) revoke(url)
  assetUrls.value = {}
  mode.value = 'none'
  text.value = ''
  assetIndexes.value = []
  error.value = ''
  loading.value = false
}

function readBlobText(blob: Blob): Promise<string> {
  if (typeof blob.text === 'function') return blob.text()
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.addEventListener('load', () => resolve(String(reader.result ?? '')))
    reader.addEventListener('error', () => reject(reader.error ?? new Error('文件读取失败。')))
    reader.readAsText(blob)
  })
}

async function previewSource(): Promise<void> {
  resetPreview()
  const requestGeneration = generation
  const controller = new AbortController()
  previewController = controller
  loading.value = true
  try {
    const response = await documentsApi.source(props.knowledgeBaseId, props.document.id, controller.signal)
    const isPdf = response.contentType === 'application/pdf'
      || props.document.filename.toLowerCase().endsWith('.pdf')
    if (isPdf) {
      const url = URL.createObjectURL(response.blob)
      if (requestGeneration !== generation || controller.signal.aborted) {
        URL.revokeObjectURL(url)
        return
      }
      revoke(previewUrl.value)
      previewUrl.value = url
      mode.value = 'pdf'
    } else {
      const sourceText = await readBlobText(response.blob)
      if (requestGeneration !== generation || controller.signal.aborted) return
      text.value = sourceText
      mode.value = 'text'
    }
  } catch (reason) {
    if (requestGeneration === generation && !controller.signal.aborted) error.value = messageFor(reason)
  } finally {
    if (requestGeneration === generation && previewController === controller) {
      previewController = null
      loading.value = false
    }
  }
}

function parsedText(payload: unknown): string {
  if (typeof payload !== 'object' || payload === null) return JSON.stringify(payload, null, 2)
  const record = payload as Record<string, unknown>
  if (typeof record.markdown === 'string') return record.markdown
  if (Array.isArray(record.blocks)) {
    return record.blocks
      .map((block) => typeof block === 'object' && block !== null && typeof (block as Record<string, unknown>).text === 'string'
        ? (block as Record<string, unknown>).text as string
        : '')
      .filter(Boolean)
      .join('\n\n')
  }
  return JSON.stringify(payload, null, 2)
}

function parsedAssetIndexes(payload: unknown): number[] {
  if (typeof payload !== 'object' || payload === null) return []
  const assets = (payload as Record<string, unknown>).assets
  if (!Array.isArray(assets)) return []
  return [...new Set(assets.flatMap((asset) => {
    if (typeof asset !== 'object' || asset === null) return []
    const index = (asset as Record<string, unknown>).asset_index
    return Number.isInteger(index) && (index as number) >= 0 ? [index as number] : []
  }))]
}

async function previewParsed(): Promise<void> {
  resetPreview()
  const requestGeneration = generation
  const controller = new AbortController()
  previewController = controller
  loading.value = true
  try {
    const response = await documentsApi.parsed(props.knowledgeBaseId, props.document.id, controller.signal)
    const payload: unknown = JSON.parse(await readBlobText(response.blob))
    if (requestGeneration !== generation || controller.signal.aborted) return
    text.value = parsedText(payload)
    assetIndexes.value = parsedAssetIndexes(payload)
    mode.value = 'text'
  } catch (reason) {
    if (requestGeneration === generation && !controller.signal.aborted) error.value = messageFor(reason)
  } finally {
    if (requestGeneration === generation && previewController === controller) {
      previewController = null
      loading.value = false
    }
  }
}

async function previewAsset(assetIndex: number): Promise<void> {
  if (!assetIndexes.value.includes(assetIndex) || assetUrls.value[assetIndex] || assetControllers.has(assetIndex)) return
  const requestGeneration = generation
  const controller = new AbortController()
  assetControllers.set(assetIndex, controller)
  try {
    const response = await documentsApi.image(props.knowledgeBaseId, props.document.id, assetIndex, controller.signal)
    const url = URL.createObjectURL(response.blob)
    if (requestGeneration !== generation || controller.signal.aborted || assetControllers.get(assetIndex) !== controller) {
      URL.revokeObjectURL(url)
      return
    }
    if (assetUrls.value[assetIndex]) {
      URL.revokeObjectURL(url)
      return
    }
    assetUrls.value = { ...assetUrls.value, [assetIndex]: url }
  } catch (reason) {
    if (requestGeneration === generation && !controller.signal.aborted) error.value = messageFor(reason)
  } finally {
    if (assetControllers.get(assetIndex) === controller) assetControllers.delete(assetIndex)
  }
}

async function download(kind: 'source' | 'parsed', fallbackName: string): Promise<void> {
  const requestGeneration = generation
  const controller = new AbortController()
  downloadControllers.add(controller)
  try {
    const response: BlobResponse = await documentsApi[kind](props.knowledgeBaseId, props.document.id, controller.signal)
    const url = URL.createObjectURL(response.blob)
    if (requestGeneration !== generation || controller.signal.aborted) {
      URL.revokeObjectURL(url)
      return
    }
    const anchor = window.document.createElement('a')
    anchor.href = url
    anchor.download = response.filename ?? fallbackName
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (reason) {
    if (requestGeneration === generation && !controller.signal.aborted) error.value = messageFor(reason)
  } finally {
    downloadControllers.delete(controller)
  }
}

watch(() => props.document.id, resetPreview)
onBeforeUnmount(resetPreview)
</script>

<template>
  <section class="document-preview" aria-labelledby="document-preview-title">
    <div class="document-preview__heading">
      <div>
        <p class="document-preview__eyebrow">文档预览</p>
        <h2 id="document-preview-title">{{ document.filename }}</h2>
      </div>
      <div class="document-preview__actions">
        <button name="preview-source" type="button" class="button button--secondary" @click="previewSource">预览原文</button>
        <button name="preview-parsed" type="button" class="button button--secondary" :disabled="!document.parsed_object_key" @click="previewParsed">预览解析结果</button>
        <button type="button" class="button button--secondary" @click="download('source', document.filename)">下载原文</button>
        <button type="button" class="button button--secondary" :disabled="!document.parsed_object_key" @click="download('parsed', `${document.filename}.json`)">下载解析结果</button>
      </div>
    </div>

    <p v-if="loading" role="status">正在加载预览…</p>
    <p v-if="error" class="document-preview__error" role="alert">{{ error }}</p>
    <pre v-if="mode === 'text'" class="document-preview__text">{{ text }}</pre>
    <object v-else-if="mode === 'pdf' && previewUrl" class="document-preview__pdf" :data="previewUrl" type="application/pdf">
      <p>浏览器无法直接预览 PDF。<a :href="previewUrl" :download="document.filename">下载 PDF</a></p>
    </object>

    <div v-if="assetIndexes.length" class="document-preview__assets">
      <h3>解析图片</h3>
      <div v-for="assetIndex in assetIndexes" :key="assetIndex" class="document-preview__asset">
        <button name="preview-asset" type="button" class="button button--secondary" @click="previewAsset(assetIndex)">图片 {{ assetIndex }}</button>
        <img v-if="assetUrls[assetIndex]" :src="assetUrls[assetIndex]" :alt="`解析图片 ${assetIndex}`">
      </div>
    </div>
  </section>
</template>

<style scoped>
.document-preview { display: grid; gap: 1rem; padding: 1rem; border: 1px solid var(--color-border); border-radius: 0.75rem; background: var(--color-page); }
.document-preview__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.document-preview__eyebrow, .document-preview h2, .document-preview h3, .document-preview p { margin: 0; }
.document-preview__eyebrow { margin-bottom: 0.25rem; color: var(--color-text-muted); font-size: 0.8125rem; }
.document-preview__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.5rem; }
.document-preview__error { color: var(--color-destructive); }
.document-preview__text { overflow: auto; max-height: 28rem; margin: 0; padding: 1rem; border-radius: 0.5rem; white-space: pre-wrap; overflow-wrap: anywhere; background: var(--color-surface); }
.document-preview__pdf { width: 100%; height: 32rem; border: 1px solid var(--color-border); background: var(--color-surface); }
.document-preview__assets { display: grid; gap: 0.75rem; }
.document-preview__asset { display: grid; justify-items: start; gap: 0.75rem; }
.document-preview__asset img { max-width: min(100%, 36rem); max-height: 28rem; border: 1px solid var(--color-border); border-radius: 0.5rem; }

@media (max-width: 44rem) {
  .document-preview__heading { display: grid; }
  .document-preview__actions { justify-content: flex-start; }
}
</style>
