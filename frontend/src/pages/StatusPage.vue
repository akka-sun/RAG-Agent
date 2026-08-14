<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ApiError } from '@/api/client'
import { healthApi } from '@/api/resources'
import { useNotificationStore } from '@/stores/notifications'

type ApiStatus = 'unknown' | 'checking' | 'healthy' | 'disconnected'

const notifications = useNotificationStore()
const apiStatus = ref<ApiStatus>('unknown')
const latency = ref<number | null>(null)
const lastChecked = ref<Date | null>(null)
const detail = ref<string | null>(null)
const checking = ref(false)
let generation = 0

const apiLabel = computed(() => ({
  unknown: '尚未检查',
  checking: '检查中',
  healthy: 'API 正常',
  disconnected: 'API 已断开',
}[apiStatus.value]))

function errorDetail(error: unknown): string {
  if (error instanceof ApiError) return `API 请求失败（HTTP ${error.status}），请稍后重试`
  return '无法连接到 API，请检查网络后重试'
}

async function check(): Promise<void> {
  if (checking.value) return
  const currentGeneration = ++generation
  checking.value = true
  apiStatus.value = 'checking'
  detail.value = null
  const startedAt = performance.now()

  try {
    const response = await healthApi.live()
    if (currentGeneration !== generation) return
    latency.value = Math.round(performance.now() - startedAt)
    lastChecked.value = new Date()
    if (response?.status === 'ok') {
      apiStatus.value = 'healthy'
      notifications.push({ level: 'success', message: 'API 连接正常' })
    } else {
      apiStatus.value = 'disconnected'
      detail.value = 'API 返回了无法确认的状态'
      notifications.push({ level: 'error', message: detail.value })
    }
  } catch (error) {
    if (currentGeneration !== generation) return
    latency.value = Math.round(performance.now() - startedAt)
    lastChecked.value = new Date()
    apiStatus.value = 'disconnected'
    detail.value = errorDetail(error)
    notifications.push({ level: 'error', message: detail.value })
  } finally {
    if (currentGeneration === generation) checking.value = false
  }
}

onMounted(() => { void check() })
onUnmounted(() => { generation += 1 })
</script>

<template>
  <section class="page status-page" aria-labelledby="status-title">
    <p class="page__eyebrow">运行状态</p>
    <h1 id="status-title">系统状态</h1>
    <p class="page__description">查看当前页面和 API 的真实连接状态。</p>

    <div class="status-page__grid">
      <article class="status-card">
        <h2>前端</h2>
        <p class="status-card__value status-card__value--healthy">本地已加载</p>
      </article>
      <article class="status-card" :aria-busy="checking">
        <h2>代理 / API</h2>
        <p class="status-card__value" :class="`status-card__value--${apiStatus}`">{{ apiLabel }}</p>
        <p v-if="latency !== null" class="status-card__meta">{{ latency }} ms</p>
        <p v-if="detail" class="status-card__detail" role="alert">{{ detail }}</p>
        <button class="button" type="button" :disabled="checking" @click="check()">
          {{ checking ? '检查中…' : apiStatus === 'disconnected' ? '重试' : '重新检查' }}
        </button>
      </article>
    </div>

    <p v-if="lastChecked" class="status-page__checked">最后检查：{{ lastChecked.toLocaleTimeString() }}</p>

    <section class="status-page__infrastructure" aria-labelledby="infrastructure-title">
      <h2 id="infrastructure-title">基础设施</h2>
      <p>以下服务尚无可用的后端检测接口，因此不会推断它们的运行状态。</p>
      <ul>
        <li v-for="service in ['PostgreSQL', 'Redis', 'MinIO', 'Milvus']" :key="service">
          <strong>{{ service }}</strong><span>后端未提供检测接口</span>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.status-page__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 1rem; margin-top: 1.5rem; }
.status-card, .status-page__infrastructure { padding: 1.25rem; border: 1px solid var(--color-border); border-radius: 0.75rem; background: white; }
.status-card h2, .status-page__infrastructure h2 { margin-top: 0; font-size: 1rem; }
.status-card__value { margin: 0.25rem 0; font-weight: 700; }
.status-card__value--healthy { color: #15803d; }
.status-card__value--disconnected { color: var(--color-destructive); }
.status-card__value--checking, .status-card__value--unknown { color: #475569; }
.status-card__meta, .status-card__detail, .status-page__checked { color: #475569; }
.status-card__detail { color: var(--color-destructive); }
.status-page__checked { margin-top: 1rem; }
.status-page__infrastructure { margin-top: 1rem; }
.status-page__infrastructure ul { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: 0.75rem; padding: 0; list-style: none; }
.status-page__infrastructure li { display: grid; gap: 0.25rem; }
.status-page__infrastructure li span { color: #64748b; font-size: 0.875rem; }
</style>
