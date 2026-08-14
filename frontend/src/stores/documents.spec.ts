import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useDocumentStore } from './documents'
import type { DocumentRecord, IngestionTask, TaskStatus } from '@/types/api'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
  get: vi.fn(),
  source: vi.fn(),
  parsed: vi.fn(),
  image: vi.fn(),
  retry: vi.fn(),
  delete: vi.fn(),
  task: vi.fn(),
}))

vi.mock('@/api/resources', () => ({ documentsApi: api }))

const documentRecord: DocumentRecord = {
  id: 'document-id',
  knowledge_base_id: 'knowledge-base-id',
  filename: 'notes.txt',
  content_type: 'text/plain',
  size_bytes: 12,
  parser_name: 'local',
  source_object_key: 'source-key',
  parsed_object_key: 'parsed-key',
  status: 'completed',
  chunk_count: 2,
  error: null,
  created_at: '2026-08-14T00:00:00Z',
  updated_at: '2026-08-14T00:01:00Z',
}

function task(status: TaskStatus, progress = 0): IngestionTask {
  return {
    id: 'task-id',
    document_id: 'document-id',
    arq_job_id: 'job-id',
    status,
    stage: status === 'pending' ? 'queued' : 'parsing',
    progress,
    error: status === 'failed' ? '解析器不可用' : null,
    created_at: '2026-08-14T00:00:00Z',
    started_at: status === 'pending' ? null : '2026-08-14T00:00:01Z',
    completed_at: status === 'completed' || status === 'failed'
      ? '2026-08-14T00:00:06Z'
      : null,
  }
}

describe('document store polling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    setActivePinia(createPinia())
    api.upload.mockResolvedValue({
      document_id: 'document-id',
      task_id: 'task-id',
      status: 'pending',
    })
    api.list.mockResolvedValue([documentRecord])
  })

  it('keeps accepted IDs and polls after 1s, 2s, 3s, 4s, then caps at 5s', async () => {
    api.task.mockResolvedValue(task('processing', 20))
    const store = useDocumentStore()

    await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))

    expect(store.tasks['task-id']).toMatchObject({
      taskId: 'task-id',
      documentId: 'document-id',
      knowledgeBaseId: 'knowledge-base-id',
    })
    await vi.advanceTimersByTimeAsync(999)
    expect(api.task).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1_999)
    expect(api.task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(2_999)
    expect(api.task).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(3_999)
    expect(api.task).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(4)
    await vi.advanceTimersByTimeAsync(4_999)
    expect(api.task).toHaveBeenCalledTimes(4)
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(5)
    await vi.advanceTimersByTimeAsync(4_999)
    expect(api.task).toHaveBeenCalledTimes(5)
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(6)

    store.stopAllPolling()
  })

  it.each(['completed', 'failed'] as const)(
    'stops on %s and refreshes that knowledge base exactly once',
    async (status) => {
      api.task.mockResolvedValue(task(status, 100))
      const store = useDocumentStore()
      await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))

      await vi.advanceTimersByTimeAsync(1_000)
      await vi.advanceTimersByTimeAsync(20_000)

      expect(api.task).toHaveBeenCalledTimes(1)
      expect(api.list).toHaveBeenCalledTimes(1)
      expect(api.list).toHaveBeenCalledWith('knowledge-base-id')
      expect(store.tasks['task-id'].task?.status).toBe(status)
    },
  )

  it('stops after five consecutive network failures and exposes a recovery action', async () => {
    api.task.mockRejectedValue(new TypeError('network down'))
    const store = useDocumentStore()
    await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))

    await vi.advanceTimersByTimeAsync(15_000)
    await vi.advanceTimersByTimeAsync(30_000)

    expect(api.task).toHaveBeenCalledTimes(5)
    expect(store.tasks['task-id'].pollingError).toBe('任务状态获取失败，请检查网络后刷新页面重试。')
  })

  it('clears scheduled work and aborts an in-flight request during teardown', async () => {
    let requestSignal: AbortSignal | undefined
    api.task.mockImplementation((_taskId: string, signal?: AbortSignal) => {
      requestSignal = signal
      return new Promise((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      })
    })
    const store = useDocumentStore()
    await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))
    await vi.advanceTimersByTimeAsync(1_000)

    store.stopAllPolling()
    await vi.advanceTimersByTimeAsync(30_000)

    expect(requestSignal?.aborted).toBe(true)
    expect(api.task).toHaveBeenCalledTimes(1)
    expect(api.list).not.toHaveBeenCalled()
  })

  it('forwards a selected PDF parser to the multipart API boundary', async () => {
    const store = useDocumentStore()
    const file = new File(['pdf'], 'report.pdf', { type: 'application/pdf' })

    await store.upload('knowledge-base-id', file, 'mineru')

    expect(api.upload).toHaveBeenCalledWith('knowledge-base-id', file, 'mineru')
    store.stopAllPolling()
  })

  it('tracks a backend retry task and resumes polling it', async () => {
    api.retry.mockResolvedValue(task('pending'))
    api.task.mockResolvedValue(task('processing', 10))
    const store = useDocumentStore()

    await store.retry('knowledge-base-id', 'document-id')
    await vi.advanceTimersByTimeAsync(1_000)

    expect(store.tasks['task-id'].task?.status).toBe('processing')
    expect(api.task).toHaveBeenCalledWith('task-id', expect.any(AbortSignal))
    store.stopAllPolling()
  })

  it('deletes a document only after the API succeeds', async () => {
    api.delete.mockResolvedValue(undefined)
    const store = useDocumentStore()
    store.documentsByKnowledgeBase['knowledge-base-id'] = [documentRecord]

    await store.remove('knowledge-base-id', 'document-id')

    expect(api.delete).toHaveBeenCalledWith('knowledge-base-id', 'document-id')
    expect(store.documentsByKnowledgeBase['knowledge-base-id']).toEqual([])
  })

  it('keeps polling and exposes the backend error when deletion is rejected', async () => {
    api.delete.mockRejectedValue(new Error('摄取中的文档不能删除'))
    api.task.mockResolvedValue(task('processing', 30))
    const store = useDocumentStore()
    await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))

    await expect(store.remove('knowledge-base-id', 'document-id')).rejects.toThrow('摄取中的文档不能删除')
    await vi.advanceTimersByTimeAsync(1_000)

    expect(store.error).toBe('摄取中的文档不能删除')
    expect(api.task).toHaveBeenCalledTimes(1)
    expect(store.tasks['task-id']).toBeDefined()
    store.stopAllPolling()
  })

  it('removes tracked tasks only after deletion succeeds', async () => {
    api.delete.mockResolvedValue(undefined)
    const store = useDocumentStore()
    await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))

    await store.remove('knowledge-base-id', 'document-id')
    await vi.advanceTimersByTimeAsync(10_000)

    expect(store.tasks['task-id']).toBeUndefined()
    expect(api.task).not.toHaveBeenCalled()
  })

  it('resumes only eligible known tasks for one knowledge base', async () => {
    const store = useDocumentStore()
    store.tasks['pending-task'] = {
      taskId: 'pending-task', documentId: 'pending-document', knowledgeBaseId: 'knowledge-base-id',
      task: { ...task('pending'), id: 'pending-task', document_id: 'pending-document' }, pollingError: null,
    }
    store.tasks['terminal-task'] = {
      taskId: 'terminal-task', documentId: 'terminal-document', knowledgeBaseId: 'knowledge-base-id',
      task: { ...task('completed', 100), id: 'terminal-task', document_id: 'terminal-document' }, pollingError: null,
    }
    store.tasks['errored-task'] = {
      taskId: 'errored-task', documentId: 'errored-document', knowledgeBaseId: 'knowledge-base-id',
      task: { ...task('processing'), id: 'errored-task', document_id: 'errored-document' }, pollingError: '刷新页面重试',
    }
    store.tasks['other-task'] = {
      taskId: 'other-task', documentId: 'other-document', knowledgeBaseId: 'other-kb',
      task: { ...task('processing'), id: 'other-task', document_id: 'other-document' }, pollingError: null,
    }
    api.task.mockResolvedValue(task('processing', 50))

    store.resumePolling('knowledge-base-id')
    await vi.advanceTimersByTimeAsync(1_000)

    expect(api.task).toHaveBeenCalledTimes(1)
    expect(api.task).toHaveBeenCalledWith('pending-task', expect.any(AbortSignal))
    store.stopAllPolling()
  })
})
