import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import { useNotificationStore } from '@/stores/notifications'
import StatusPage from './StatusPage.vue'
import ToastHost from '@/components/common/ToastHost.vue'

const healthApi = vi.hoisted(() => ({ live: vi.fn() }))

vi.mock('@/api/resources', () => ({ healthApi }))

interface StatusState {
  apiStatus: string
  latency: number | null
  lastChecked: Date | null
  detail: string | null
}

function statusState(wrapper: ReturnType<typeof mount>): StatusState {
  return (wrapper.vm.$ as unknown as { setupState: StatusState }).setupState
}

function snapshot(state: StatusState) {
  return {
    apiStatus: state.apiStatus,
    latency: state.latency,
    lastChecked: state.lastChecked,
    detail: state.detail,
  }
}

describe('StatusPage', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.resetAllMocks()
  })

  afterEach(() => document.body.replaceChildren())

  it('shows local frontend status and marks the API healthy only after an ok live response', async () => {
    healthApi.live.mockResolvedValue({ status: 'ok' })
    const wrapper = mount(StatusPage, { global: { plugins: [pinia] } })

    await flushPromises()

    expect(wrapper.text()).toContain('本地已加载')
    expect(wrapper.text()).toContain('API 正常')
    expect(wrapper.text()).toMatch(/\d+ ms/)
    expect(wrapper.text()).toContain('最后检查')
    expect(wrapper.text()).toContain('后端未提供检测接口')
    expect(wrapper.text()).not.toContain('PostgreSQL 正常')
    expect(wrapper.text()).not.toContain('Redis 正常')
    expect(wrapper.text()).not.toContain('MinIO 正常')
    expect(wrapper.text()).not.toContain('Milvus 正常')
  })

  it('normalizes a failed health check, sends an error notification, and retries on demand', async () => {
    healthApi.live
      .mockRejectedValueOnce(new ApiError(503, 'service_unavailable', '服务暂不可用'))
      .mockResolvedValueOnce({ status: 'ok' })
    const wrapper = mount(StatusPage, { attachTo: document.body, global: { plugins: [pinia] } })

    await flushPromises()

    expect(wrapper.text()).toContain('API 已断开')
    expect(wrapper.text()).toContain('API 请求失败（HTTP 503），请稍后重试')
    expect(wrapper.get('button').text()).toContain('重试')
    expect(useNotificationStore(pinia).items[0]).toMatchObject({
      level: 'error', message: 'API 请求失败（HTTP 503），请稍后重试',
    })

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('API 正常')
    expect(healthApi.live).toHaveBeenCalledTimes(2)
  })

  it('does not start an overlapping check while a real health request is pending', async () => {
    let resolveFirst!: (value: { status: 'ok' }) => void
    healthApi.live.mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve }))
    const wrapper = mount(StatusPage, { global: { plugins: [pinia] } })

    await wrapper.get('button').trigger('click')
    expect(healthApi.live).toHaveBeenCalledTimes(1)
    resolveFirst({ status: 'ok' })
    await flushPromises()

    expect(wrapper.text()).toContain('API 正常')
    expect(wrapper.text()).toContain('最后检查')
  })

  it('normalizes generic network failures without showing browser error text', async () => {
    healthApi.live.mockRejectedValue(new TypeError('Failed to fetch'))
    const wrapper = mount(StatusPage, { global: { plugins: [pinia] } })

    await flushPromises()

    expect(wrapper.text()).toContain('无法连接到 API，请检查网络后重试')
    expect(wrapper.text()).not.toContain('Failed to fetch')
    expect(useNotificationStore(pinia).items[0]).toMatchObject({
      level: 'error', message: '无法连接到 API，请检查网络后重试',
    })
  })

  it('normalizes a default English HTTP ApiError without exposing it in the card or toast', async () => {
    healthApi.live.mockRejectedValue(new ApiError(502, 'http_error', 'Request failed with status 502'))
    const wrapper = mount(StatusPage, { global: { plugins: [pinia] } })

    await flushPromises()

    expect(wrapper.text()).toContain('API 请求失败（HTTP 502），请稍后重试')
    expect(wrapper.text()).not.toContain('Request failed with status 502')
    expect(useNotificationStore(pinia).items[0]).toMatchObject({
      level: 'error', message: 'API 请求失败（HTTP 502），请稍后重试',
    })
  })

  it('ignores a deferred success after unmount without changing the old status state or notifications', async () => {
    let resolve!: (response: { status: 'ok' }) => void
    healthApi.live.mockReturnValue(new Promise((done) => { resolve = done }))
    const wrapper = mount(StatusPage, { global: { plugins: [pinia] } })
    const state = statusState(wrapper)
    const before = snapshot(state)

    wrapper.unmount()
    resolve({ status: 'ok' })
    await flushPromises()

    expect(snapshot(state)).toEqual(before)
    expect(useNotificationStore(pinia).items).toEqual([])
  })

  it('ignores a deferred failure after unmount without changing the old status state or notifications', async () => {
    let reject!: (reason: unknown) => void
    healthApi.live.mockReturnValue(new Promise((_done, fail) => { reject = fail }))
    const wrapper = mount(StatusPage, { global: { plugins: [pinia] } })
    const state = statusState(wrapper)
    const before = snapshot(state)

    wrapper.unmount()
    reject(new ApiError(502, 'http_error', 'Request failed with status 502'))
    await flushPromises()

    expect(snapshot(state)).toEqual(before)
    expect(useNotificationStore(pinia).items).toEqual([])
  })
})

describe('ToastHost', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })
  afterEach(() => document.body.replaceChildren())

  it('announces routine and error notifications with appropriate live roles without moving focus', async () => {
    const store = useNotificationStore(pinia)
    const trigger = document.createElement('button')
    document.body.append(trigger)
    trigger.focus()
    store.push({ level: 'success', message: 'Saved', duration: 0 })
    store.push({ level: 'error', message: 'Failed' })
    const wrapper = mount(ToastHost, { attachTo: document.body, global: { plugins: [pinia] } })

    await flushPromises()

    expect(wrapper.get('[role="status"]').text()).toContain('Saved')
    expect(wrapper.get('[role="alert"]').text()).toContain('Failed')
    expect(wrapper.find('button[aria-label="关闭通知：Failed"]').exists()).toBe(true)
    expect(document.activeElement).toBe(trigger)
  })
})
