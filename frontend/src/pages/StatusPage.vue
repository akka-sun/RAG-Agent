<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ApiError } from '@/api/client'
import { healthApi } from '@/api/resources'
import { useNotificationStore } from '@/stores/notifications'
import type { InfrastructureServiceName, ReadinessResponse, ServiceReadiness } from '@/types/api'

type ApiStatus = 'unknown' | 'checking' | 'healthy' | 'disconnected'
type DependencyStatus = 'unknown' | 'checking' | 'healthy' | 'unhealthy' | 'unavailable'
type ReadinessStatus = 'unknown' | 'checking' | ReadinessResponse['status'] | 'unavailable'

interface DependencyState {
  status: DependencyStatus
  latency: number | null
  error: string | null
}

const serviceDefinitions: Array<{ key: InfrastructureServiceName, label: string }> = [
  { key: 'postgresql', label: 'PostgreSQL' },
  { key: 'redis', label: 'Redis' },
  { key: 'minio', label: 'MinIO' },
  { key: 'milvus', label: 'Milvus' },
]

const dependencyStatusLabels: Record<DependencyStatus, string> = {
  unknown: '尚未检查',
  checking: '检查中',
  healthy: '正常',
  unhealthy: '异常',
  unavailable: '无法检测',
}

const readinessStatusLabels: Record<ReadinessStatus, string> = {
  unknown: '尚未检查',
  checking: '检查中',
  healthy: '全部正常',
  degraded: '部分异常',
  unavailable: '无法检测',
}

function newDependencyState(): DependencyState {
  return { status: 'unknown', latency: null, error: null }
}

const notifications = useNotificationStore()
const apiStatus = ref<ApiStatus>('unknown')
const latency = ref<number | null>(null)
const lastChecked = ref<Date | null>(null)
const detail = ref<string | null>(null)
const checking = ref(false)
const readinessStatus = ref<ReadinessStatus>('unknown')
const readinessDetail = ref<string | null>(null)
const dependencyStates = reactive(Object.fromEntries(
  serviceDefinitions.map(({ key }) => [key, newDependencyState()]),
) as Record<InfrastructureServiceName, DependencyState>)
const infrastructureServices = computed(() => serviceDefinitions.map(({ key, label }) => ({
  key,
  label,
  ...dependencyStates[key],
  statusLabel: dependencyStatusLabels[dependencyStates[key].status],
})))
const readinessLabel = computed(() => readinessStatusLabels[readinessStatus.value])
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

function readinessErrorDetail(): string {
  return '无法检测基础设施状态，请稍后重试'
}

function safeServiceError(service: string, error: unknown): string {
  if (typeof error !== 'string' || !error.trim() || /:\/\/|token|password|secret/i.test(error)) {
    return `${service} 检查失败`
  }
  return error.replace(/\s+/g, ' ').slice(0, 200)
}

function setDependencyState(name: InfrastructureServiceName, state: DependencyState): void {
  Object.assign(dependencyStates[name], state)
}

function beginReadinessCheck(): void {
  readinessStatus.value = 'checking'
  readinessDetail.value = null
  for (const { key } of serviceDefinitions) {
    setDependencyState(key, { status: 'checking', latency: null, error: null })
  }
}

async function checkLive(currentGeneration: number): Promise<void> {
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
  }
}

async function checkReadiness(currentGeneration: number): Promise<void> {
  try {
    const response = await healthApi.ready()
    if (currentGeneration !== generation) return

    readinessStatus.value = response?.status === 'healthy' ? 'healthy' : 'degraded'
    for (const { key, label } of serviceDefinitions) {
      const service: ServiceReadiness | undefined = response?.services?.[key]
      if (!service) {
        setDependencyState(key, { status: 'unhealthy', latency: null, error: `${label} 未返回状态` })
        continue
      }
      const status = service.status === 'healthy' ? 'healthy' : 'unhealthy'
      setDependencyState(key, {
        status,
        latency: Number.isFinite(service.latency_ms) ? Math.max(0, service.latency_ms) : null,
        error: status === 'healthy' ? null : safeServiceError(label, service.error),
      })
    }
  } catch {
    if (currentGeneration !== generation) return
    readinessStatus.value = 'unavailable'
    readinessDetail.value = readinessErrorDetail()
    for (const { key } of serviceDefinitions) {
      setDependencyState(key, { status: 'unavailable', latency: null, error: null })
    }
  }
}

async function check(): Promise<void> {
  if (checking.value) return
  const currentGeneration = ++generation
  checking.value = true
  apiStatus.value = 'checking'
  detail.value = null
  beginReadinessCheck()

  try {
    await Promise.all([checkLive(currentGeneration), checkReadiness(currentGeneration)])
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

    <section class="status-page__infrastructure" aria-labelledby="infrastructure-title" :aria-busy="readinessStatus === 'checking'">
      <h2 id="infrastructure-title">基础设施</h2>
      <p class="status-page__infrastructure-summary">就绪状态：{{ readinessLabel }}</p>
      <p v-if="readinessDetail" class="status-card__detail" role="alert">{{ readinessDetail }}</p>
      <ul>
        <li
          v-for="service in infrastructureServices"
          :key="service.key"
          :data-service="service.key"
          :data-status="service.status"
        >
          <strong>{{ service.label }}</strong>
          <span class="status-page__service-value" :class="`status-page__service-value--${service.status}`">{{ service.statusLabel }}</span>
          <span v-if="service.latency !== null" class="status-page__service-meta">{{ service.latency }} ms</span>
          <span v-if="service.error" class="status-page__service-error">{{ service.error }}</span>
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
.status-card__meta, .status-card__detail, .status-page__checked, .status-page__infrastructure-summary { color: #475569; }
.status-card__detail { color: var(--color-destructive); }
.status-page__checked { margin-top: 1rem; }
.status-page__infrastructure { margin-top: 1rem; }
.status-page__infrastructure ul { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: 0.75rem; padding: 0; list-style: none; }
.status-page__infrastructure li { display: grid; align-content: start; gap: 0.25rem; min-height: 5.5rem; padding: 0.75rem 0; border-top: 1px solid var(--color-border); }
.status-page__infrastructure li span { font-size: 0.875rem; }
.status-page__service-value { font-weight: 700; }
.status-page__service-value--healthy { color: #15803d; }
.status-page__service-value--unhealthy { color: var(--color-destructive); }
.status-page__service-value--checking, .status-page__service-value--unknown, .status-page__service-value--unavailable, .status-page__service-meta { color: #64748b; }
.status-page__service-error { color: var(--color-destructive); overflow-wrap: anywhere; }
</style>
