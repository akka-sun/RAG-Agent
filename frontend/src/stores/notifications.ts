import { ref } from 'vue'
import { defineStore } from 'pinia'

export type NotificationLevel = 'info' | 'success' | 'warning' | 'error'

export interface NotificationInput {
  level: NotificationLevel
  message: string
  duration?: number
}

export interface Notification extends Required<Omit<NotificationInput, 'duration'>> {
  id: string
  duration?: number
}

const MAX_NOTIFICATIONS = 5
const DEFAULT_DURATION = 5000
let nextNotificationId = 0

export const useNotificationStore = defineStore('notifications', () => {
  const items = ref<Notification[]>([])
  const timers = new Map<string, ReturnType<typeof setTimeout>>()

  function push(input: NotificationInput): string {
    const id = `notification-${Date.now()}-${++nextNotificationId}`
    const duration = input.duration ?? (input.level === 'error' ? undefined : DEFAULT_DURATION)
    const notification: Notification = { id, level: input.level, message: input.message, ...(duration === undefined ? {} : { duration }) }

    if (items.value.length === MAX_NOTIFICATIONS) {
      const evicted = items.value.shift()
      if (evicted) cancelTimer(evicted.id)
    }
    items.value.push(notification)
    if (duration && duration > 0) {
      timers.set(id, setTimeout(() => dismiss(id), duration))
    }
    return id
  }

  function dismiss(id: string): void {
    cancelTimer(id)
    const index = items.value.findIndex((item) => item.id === id)
    if (index !== -1) items.value.splice(index, 1)
  }

  function clear(): void {
    for (const id of timers.keys()) cancelTimer(id)
    items.value.splice(0)
  }

  function cancelTimer(id: string): void {
    const timer = timers.get(id)
    if (timer === undefined) return
    clearTimeout(timer)
    timers.delete(id)
  }

  return { items, push, dismiss, clear }
})
