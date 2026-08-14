import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useNotificationStore } from './notifications'

describe('notification store', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('expires timed notifications while error notifications remain until dismissed', () => {
    const store = useNotificationStore()
    store.push({ level: 'success', message: 'Saved', duration: 1000 })
    store.push({ level: 'error', message: 'Connection failed' })

    vi.advanceTimersByTime(1000)

    expect(store.items.map((item) => item.message)).toEqual(['Connection failed'])
    expect(vi.getTimerCount()).toBe(0)
  })

  it('cancels an expiry timer when a notification is manually dismissed', () => {
    const store = useNotificationStore()
    const id = store.push({ level: 'info', message: 'Checking', duration: 1000 })

    store.dismiss(id)
    vi.advanceTimersByTime(1000)

    expect(store.items).toEqual([])
    expect(vi.getTimerCount()).toBe(0)
  })

  it('uses distinct IDs for notifications created in the same clock tick', () => {
    const store = useNotificationStore()
    vi.setSystemTime(new Date('2026-08-14T00:00:00Z'))

    const first = store.push({ level: 'info', message: 'First' })
    const second = store.push({ level: 'info', message: 'Second' })

    expect(first).not.toBe(second)
    expect(store.items).toHaveLength(2)
  })

  it('cleans timers for evicted and cleared notifications', () => {
    const store = useNotificationStore()
    for (let index = 0; index < 6; index += 1) {
      store.push({ level: 'info', message: `Notification ${index}`, duration: 1000 })
    }

    expect(store.items.map((item) => item.message)).toEqual([
      'Notification 1', 'Notification 2', 'Notification 3', 'Notification 4', 'Notification 5',
    ])
    expect(vi.getTimerCount()).toBe(5)
    store.clear()

    expect(store.items).toEqual([])
    expect(vi.getTimerCount()).toBe(0)
  })
})
