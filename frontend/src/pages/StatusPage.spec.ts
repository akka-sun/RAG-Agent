import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import { useNotificationStore } from '@/stores/notifications'
import StatusPage from './StatusPage.vue'
import ToastHost from '@/components/common/ToastHost.vue'

const healthApi = vi.hoisted(() => ({ live: vi.fn() }))

vi.mock('@/api/resources', () => ({ healthApi }))

describe('StatusPage', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
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
    expect(wrapper.text()).toContain('服务暂不可用')
    expect(wrapper.get('button').text()).toContain('重试')
    expect(useNotificationStore(pinia).items[0]).toMatchObject({ level: 'error', message: '服务暂不可用' })

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
