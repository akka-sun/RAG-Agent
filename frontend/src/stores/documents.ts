import { onScopeDispose, ref } from 'vue'
import { defineStore } from 'pinia'
import { documentsApi } from '@/api/resources'
import type { DocumentRecord, IngestionTask } from '@/types/api'

const MAX_POLL_FAILURES = 5

export interface TrackedIngestionTask {
  taskId: string
  documentId: string
  knowledgeBaseId: string
  task: IngestionTask | null
  pollingError: string | null
}

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请稍后重试。'
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export const useDocumentStore = defineStore('documents', () => {
  const documentsByKnowledgeBase = ref<Record<string, DocumentRecord[]>>({})
  const tasks = ref<Record<string, TrackedIngestionTask>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)
  const timers = new Map<string, ReturnType<typeof setTimeout>>()
  const controllers = new Map<string, AbortController>()
  const delaySteps = new Map<string, number>()
  const consecutiveFailures = new Map<string, number>()
  const refreshedTerminalTasks = new Set<string>()

  async function load(knowledgeBaseId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      documentsByKnowledgeBase.value[knowledgeBaseId] = await documentsApi.list(knowledgeBaseId) ?? []
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    } finally {
      loading.value = false
    }
  }

  function stopPolling(taskId: string): void {
    const timer = timers.get(taskId)
    if (timer !== undefined) clearTimeout(timer)
    timers.delete(taskId)
    controllers.get(taskId)?.abort()
    controllers.delete(taskId)
    delaySteps.delete(taskId)
    consecutiveFailures.delete(taskId)
  }

  function schedule(taskId: string): void {
    if (timers.has(taskId) || controllers.has(taskId)) return
    const tracked = tasks.value[taskId]
    if (!tracked || tracked.pollingError || tracked.task?.status === 'completed' || tracked.task?.status === 'failed') return
    const step = delaySteps.get(taskId) ?? 0
    const delay = Math.min(step + 1, 5) * 1_000
    delaySteps.set(taskId, step + 1)
    timers.set(taskId, setTimeout(() => {
      timers.delete(taskId)
      void poll(taskId)
    }, delay))
  }

  async function poll(taskId: string): Promise<void> {
    const tracked = tasks.value[taskId]
    if (!tracked) return
    const controller = new AbortController()
    controllers.set(taskId, controller)

    try {
      const latest = await documentsApi.task(taskId, controller.signal)
      if (controller.signal.aborted || controllers.get(taskId) !== controller) return
      if (!latest) throw new Error('任务状态响应为空。')
      tracked.task = latest
      tracked.pollingError = null
      consecutiveFailures.set(taskId, 0)
      controllers.delete(taskId)

      if (latest.status === 'completed' || latest.status === 'failed') {
        stopPolling(taskId)
        if (!refreshedTerminalTasks.has(taskId)) {
          refreshedTerminalTasks.add(taskId)
          await load(tracked.knowledgeBaseId)
        }
        return
      }
      schedule(taskId)
    } catch (reason) {
      if (controller.signal.aborted || controllers.get(taskId) !== controller || isAbort(reason)) return
      controllers.delete(taskId)
      if (!(reason instanceof TypeError)) {
        tracked.pollingError = messageFor(reason)
        stopPolling(taskId)
        return
      }
      const failures = (consecutiveFailures.get(taskId) ?? 0) + 1
      consecutiveFailures.set(taskId, failures)
      if (failures >= MAX_POLL_FAILURES) {
        tracked.pollingError = '任务状态获取失败，请检查网络后刷新页面重试。'
        stopPolling(taskId)
        return
      }
      schedule(taskId)
    }
  }

  function pollTask(taskId: string): void {
    schedule(taskId)
  }

  function resumePolling(knowledgeBaseId: string): void {
    for (const tracked of Object.values(tasks.value)) {
      if (tracked.knowledgeBaseId === knowledgeBaseId
        && !tracked.pollingError
        && tracked.task?.status !== 'completed'
        && tracked.task?.status !== 'failed') {
        pollTask(tracked.taskId)
      }
    }
  }

  function track(
    knowledgeBaseId: string,
    documentId: string,
    taskId: string,
    ingestionTask: IngestionTask | null,
  ): void {
    stopPolling(taskId)
    refreshedTerminalTasks.delete(taskId)
    tasks.value[taskId] = {
      taskId,
      documentId,
      knowledgeBaseId,
      task: ingestionTask,
      pollingError: null,
    }
    pollTask(taskId)
  }

  async function upload(
    knowledgeBaseId: string,
    file: File,
    parser?: 'local' | 'mineru' | 'paddlex',
  ): Promise<void> {
    error.value = null
    try {
      const accepted = await documentsApi.upload(knowledgeBaseId, file, parser)
      if (!accepted) throw new Error('上传任务创建失败，请稍后重试。')
      track(knowledgeBaseId, accepted.document_id, accepted.task_id, null)
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    }
  }

  async function retry(knowledgeBaseId: string, documentId: string): Promise<void> {
    error.value = null
    try {
      const ingestionTask = await documentsApi.retry(knowledgeBaseId, documentId)
      if (!ingestionTask) throw new Error('重试任务创建失败，请稍后重试。')
      track(knowledgeBaseId, ingestionTask.document_id, ingestionTask.id, ingestionTask)
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    }
  }

  async function remove(knowledgeBaseId: string, documentId: string): Promise<void> {
    error.value = null
    try {
      await documentsApi.delete(knowledgeBaseId, documentId)
      for (const tracked of Object.values(tasks.value)) {
        if (tracked.documentId !== documentId) continue
        stopPolling(tracked.taskId)
        delete tasks.value[tracked.taskId]
      }
      documentsByKnowledgeBase.value[knowledgeBaseId] = (documentsByKnowledgeBase.value[knowledgeBaseId] ?? [])
        .filter((document) => document.id !== documentId)
    } catch (reason) {
      error.value = messageFor(reason)
      throw reason
    }
  }

  function stopAllPolling(): void {
    for (const taskId of new Set([...timers.keys(), ...controllers.keys()])) stopPolling(taskId)
  }

  onScopeDispose(stopAllPolling)

  return {
    documentsByKnowledgeBase,
    tasks,
    loading,
    error,
    load,
    upload,
    pollTask,
    resumePolling,
    retry,
    remove,
    stopAllPolling,
  }
})
